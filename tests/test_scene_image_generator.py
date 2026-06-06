import base64
import json
import os
import tempfile
import unittest
from contextlib import redirect_stdout
from io import BytesIO, StringIO
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from PIL import Image

from mv_artwork_creator.cli import main
from mv_artwork_creator.scene_executor import (
    SceneGenerationConfig,
    create_scene_plan,
    run_scene_generation,
    scene_plan_to_dict,
)
from mv_artwork_creator.scene_prompts import load_scene_prompt_library
from mv_artwork_creator.web import (
    _GeneratorRequestHandler,
    list_input_dir_images,
    render_home_page,
    run_avatar_generation_from_form,
    run_avatar_dry_run_from_form,
    run_scene_dry_run_from_form,
)


PNG_RGBA_1X1 = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAFgwJ/lY8pngAAAABJRU5ErkJggg=="
)


def make_png_bytes() -> bytes:
    buffer = BytesIO()
    Image.new("RGBA", (2, 2), (255, 255, 255, 0)).save(buffer, format="PNG")
    return buffer.getvalue()


class FakeSceneClient:
    def __init__(self):
        self.requests = []

    def generate_image(self, request):
        self.requests.append(request)
        return {
            "image_bytes": make_png_bytes(),
            "mime_type": "image/png",
            "extension": ".png",
            "response_id": f"scene-{len(self.requests)}",
            "raw": {"id": f"scene-{len(self.requests)}"},
        }


class SceneImageGeneratorTests(unittest.TestCase):
    def test_scene_prompt_library_composes_brand_prompt_from_setting_and_action(self):
        library = load_scene_prompt_library(Path("mv_artwork_creator/resources/scene_prompts.yaml"))

        prompt = library.compose_prompt(
            setting="a glass-walled high-rise office overlooking Zurich at sunset",
            action="reviewing a risk dashboard on a slim tablet",
        )

        self.assertIn("attached PNG reference", prompt)
        self.assertIn("Messy stays anime in focus", prompt)
        self.assertIn("background partly photorealistic", prompt)
        self.assertIn("a glass-walled high-rise office overlooking Zurich at sunset", prompt)
        self.assertIn("reviewing a risk dashboard on a slim tablet", prompt)
        self.assertIn("Sparse OHLC charts", prompt)
        self.assertIn("Never wax candles", prompt)
        self.assertIn("No HUD", prompt)
        self.assertIn("generic anime woman", library.negative_prompt)
        self.assertIn("Wax candles", library.negative_prompt)
        self.assertIn("gender swap", library.negative_prompt)

    def test_scene_prompt_rejects_empty_setting_or_action(self):
        library = load_scene_prompt_library(Path("mv_artwork_creator/resources/scene_prompts.yaml"))

        with self.assertRaisesRegex(ValueError, "setting"):
            library.compose_prompt(setting="", action="checking charts")
        with self.assertRaisesRegex(ValueError, "action"):
            library.compose_prompt(setting="dark office", action=" ")

    def test_scene_generation_writes_metadata_resumes_and_regenerates(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "messy.png"
            output = Path(tmp) / "scenes"
            source.write_bytes(PNG_RGBA_1X1)
            library = load_scene_prompt_library(Path("mv_artwork_creator/resources/scene_prompts.yaml"))
            config = SceneGenerationConfig(
                source_image=source,
                output_dir=output,
                model="custom/scene-model",
                setting="modern trading floor with glass walls",
                action="calmly pointing at a nearby market screen",
                prompt_library=Path("mv_artwork_creator/resources/scene_prompts.yaml"),
                filename="trading-floor",
            )

            client = FakeSceneClient()
            first = run_scene_generation(config, library, client)
            second = run_scene_generation(config, library, client)
            third = run_scene_generation(config.with_updates(regenerate=True), library, client)

            metadata_path = output / "trading-floor.json"
            metadata = json.loads(metadata_path.read_text())

            self.assertEqual(1, first.generated)
            self.assertEqual(0, first.skipped)
            self.assertEqual(0, second.generated)
            self.assertEqual(1, second.skipped)
            self.assertEqual(1, third.generated)
            self.assertEqual(2, len(client.requests))
            first_request = client.requests[0]
            self.assertEqual("custom/scene-model", first_request.model)
            self.assertEqual(PNG_RGBA_1X1, first_request.source_image_bytes)
            self.assertIn("modern trading floor with glass walls", first_request.prompt)
            self.assertIn("calmly pointing at a nearby market screen", first_request.prompt)
            self.assertIn("HUD", first_request.negative_prompt)
            self.assertTrue((output / "trading-floor.png").exists())
            self.assertEqual("succeeded", metadata["status"])
            self.assertEqual("modern trading floor with glass walls", metadata["setting"])
            self.assertEqual("calmly pointing at a nearby market screen", metadata["action"])
            self.assertIn("prompt_sha256", metadata)
            self.assertTrue(metadata["openrouter_request"]["reference_image_attached"])

    def test_scene_generation_records_provider_failure_metadata(self):
        class FailingClient:
            def generate_image(self, request):
                raise RuntimeError("provider exploded")

        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "messy.png"
            output = Path(tmp) / "scenes"
            source.write_bytes(PNG_RGBA_1X1)
            library = load_scene_prompt_library(Path("mv_artwork_creator/resources/scene_prompts.yaml"))
            config = SceneGenerationConfig(
                source_image=source,
                output_dir=output,
                setting="dark city street",
                action="holding a coffee while watching a billboard",
                filename="city",
            )

            summary = run_scene_generation(config, library, FailingClient())
            metadata = json.loads((output / "city.json").read_text())

            self.assertEqual(0, summary.generated)
            self.assertEqual(1, summary.failed)
            self.assertEqual("failed", metadata["status"])
            self.assertIn("provider exploded", metadata["error"])

    def test_scene_dry_run_includes_openrouter_reference_attachment_summary(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "messy.png"
            source.write_bytes(make_png_bytes())
            config = SceneGenerationConfig(
                source_image=source,
                setting="neon office",
                action="reviewing a tablet",
            )
            library = load_scene_prompt_library(Path("mv_artwork_creator/resources/scene_prompts.yaml"))
            plan = create_scene_plan(config, library)
            payload = scene_plan_to_dict(plan)

            request = payload["openrouter_request"]
            self.assertIsInstance(request, dict)
            self.assertTrue(request["reference_image_attached"])
            self.assertEqual(["image_url", "text"], request["message_content_types"])
            self.assertGreater(request["reference_image_byte_size"], 0)
            self.assertEqual("image/png", request["reference_image_mime_type"])

    def test_scene_cli_dry_run_prints_prompt_without_provider_request(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "messy.png"
            source.write_bytes(PNG_RGBA_1X1)
            stdout = StringIO()

            with redirect_stdout(stdout):
                exit_code = main(
                    [
                        "scene",
                        str(source),
                        "--setting",
                        "dark office",
                        "--action",
                        "reviewing risk charts",
                        "--output-dir",
                        str(Path(tmp) / "out"),
                        "--dry-run",
                    ]
                )

            payload = json.loads(stdout.getvalue())
            self.assertEqual(0, exit_code)
            self.assertEqual("dark office", payload["setting"])
            self.assertEqual("reviewing risk charts", payload["action"])
            self.assertIn("prompt", payload)
            self.assertTrue(payload["output_path"].endswith(".png"))

    def test_scene_cli_generation_uses_client_and_prints_summary(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "messy.png"
            source.write_bytes(PNG_RGBA_1X1)
            stdout = StringIO()
            summary = SimpleNamespace(planned=1, generated=1, skipped=0, failed=0)

            with patch("mv_artwork_creator.cli.OpenRouterClient") as client_class:
                with patch("mv_artwork_creator.cli.run_scene_generation", return_value=summary) as run_scene:
                    with redirect_stdout(stdout):
                        exit_code = main(
                            [
                                "scene",
                                str(source),
                                "--setting",
                                "dark office",
                                "--action",
                                "reviewing risk charts",
                                "--output-dir",
                                str(Path(tmp) / "out"),
                                "--api-key",
                                "test-key",
                            ]
                        )

            payload = json.loads(stdout.getvalue())
            self.assertEqual(0, exit_code)
            self.assertEqual(1, payload["generated"])
            client_class.assert_called_once_with(api_key="test-key")
            self.assertEqual("dark office", run_scene.call_args.args[0].setting)
            self.assertEqual(client_class.return_value, run_scene.call_args.args[2])

    def test_scene_cli_rejects_missing_credential_before_generation_request(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "messy.png"
            source.write_bytes(PNG_RGBA_1X1)

            with patch("mv_artwork_creator.cli.load_env_file", return_value={}):
                with patch.dict(os.environ, {}, clear=True):
                    with patch("mv_artwork_creator.cli.OpenRouterClient") as client_class:
                        with self.assertRaises(SystemExit) as raised:
                            main(
                                [
                                    "scene",
                                    str(source),
                                    "--setting",
                                    "dark office",
                                    "--action",
                                    "reviewing risk charts",
                                    "--output-dir",
                                    str(Path(tmp) / "out"),
                                ]
                            )

            self.assertIn("Missing OpenRouter API credential", str(raised.exception))
            client_class.assert_not_called()

    def test_avatar_cli_dry_run_prints_plan(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "messy.png"
            source.write_bytes(PNG_RGBA_1X1)
            stdout = StringIO()

            with redirect_stdout(stdout):
                exit_code = main(["avatar", str(source), "--dry-run"])

            payload = json.loads(stdout.getvalue())
            self.assertEqual(0, exit_code)
            self.assertEqual(21, payload["planned_count"])

    def test_list_input_dir_images_ignores_hidden_and_non_images(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "messy.png").write_bytes(PNG_RGBA_1X1)
            (root / "photo.jpg").write_bytes(b"not-a-jpeg")
            (root / ".hidden.png").write_bytes(PNG_RGBA_1X1)
            (root / "notes.txt").write_text("nope")

            all_images = list_input_dir_images(root)
            png_only = list_input_dir_images(root, extensions={".png"})

            self.assertEqual([root / "messy.png", root / "photo.jpg"], all_images)
            self.assertEqual([root / "messy.png"], png_only)

    def test_render_home_page_shows_picker_without_all_workflow_forms(self):
        page = render_home_page()

        self.assertIn('class="picker"', page)
        self.assertIn('href="/?workflow=avatar"', page)
        self.assertIn('href="/?workflow=scene"', page)
        self.assertIn('href="/?workflow=messy-fy"', page)
        self.assertIn('href="/?workflow=background"', page)
        self.assertNotIn('action="/avatar"', page)
        self.assertNotIn('action="/scene"', page)
        self.assertNotIn('action="/messy-fy"', page)
        self.assertNotIn('action="/background"', page)

    def test_render_home_page_renders_focused_workflow_pages(self):
        workflows = {
            "avatar": "Avatar Reference Set",
            "scene": "Scene Generator",
            "messy-fy": "Messy-fy",
            "background": "Remove Background",
        }

        for workflow, heading in workflows.items():
            with self.subTest(workflow=workflow):
                page = render_home_page(workflow=workflow)

                self.assertIn(heading, page)
                self.assertIn('href="/"', page)
                self.assertIn(f'action="/{workflow}"', page)
                other_actions = {f'action="/{name}"' for name in workflows if name != workflow}
                self.assertTrue(all(action not in page for action in other_actions))

    def test_render_home_page_omits_generator_api_key_override_fields(self):
        for workflow in ["avatar", "scene", "messy-fy"]:
            with self.subTest(workflow=workflow):
                page = render_home_page(workflow=workflow)

                self.assertNotIn("API key override", page)
                self.assertNotIn('name="api_key"', page)

    def test_render_home_page_uses_model_alias_dropdown_defaults(self):
        avatar = render_home_page(workflow="avatar")
        messy_fy = render_home_page(workflow="messy-fy")

        self.assertIn('<select name="model"', avatar)
        self.assertIn('<option value="seedream" selected>', avatar)
        self.assertIn('<option value="nano-banana"', avatar)
        self.assertNotIn('<option value="gemini-flash"', avatar)
        self.assertNotIn('<option value="seedream-4.5"', avatar)
        self.assertIn('<select name="model"', messy_fy)
        self.assertIn('<option value="nano-banana" selected>', messy_fy)
        self.assertNotIn('<option value="gemini-flash"', messy_fy)
        self.assertNotIn('<option value="seedream-4.5"', messy_fy)

    def test_render_home_page_lists_input_directory_images_and_output_defaults(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "messy.png").write_bytes(PNG_RGBA_1X1)

            with patch("mv_artwork_creator.web.default_input_dir", return_value=root):
                page = render_home_page(workflow="avatar")

            self.assertIn('class="thumbgrid"', page)
            self.assertIn(f'data-value="{root / "messy.png"}"', page)
            self.assertIn(f'value="{root / "messy.png"}"', page)
            self.assertIn('name="source_image"', page)
            self.assertIn('value="output/avatars"', page)

    def test_web_helpers_render_scene_and_avatar_dry_runs(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "messy.png"
            source.write_bytes(PNG_RGBA_1X1)

            page = render_home_page()
            scene = run_scene_dry_run_from_form(
                {
                    "source_image": str(source),
                    "setting": "neon city avenue",
                    "action": "walking past a trading billboard",
                    "output_dir": str(Path(tmp) / "scene-out"),
                }
            )
            avatar = run_avatar_dry_run_from_form(
                {
                    "source_image": str(source),
                    "output_dir": str(Path(tmp) / "avatar-out"),
                }
            )

            self.assertIn("Messy Virgo Artwork Creator", page)
            self.assertEqual("scene-dry-run", scene["kind"])
            self.assertIn("neon city avenue", scene["prompt"])
            self.assertEqual("avatar-dry-run", avatar["kind"])
            self.assertEqual(21, avatar["planned_count"])

    def test_web_avatar_generation_uses_existing_workflow(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "messy.png"
            source.write_bytes(PNG_RGBA_1X1)

            with patch("mv_artwork_creator.web.run_generation") as run_generation:
                run_generation.return_value = SimpleNamespace(planned=1, generated=1, skipped=0, failed=0)

                result = run_avatar_generation_from_form(
                    {
                        "source_image": str(source),
                        "output_dir": str(Path(tmp) / "avatar-out"),
                        "api_key": "test-key",
                        "test_mode": "1",
                    }
                )

            self.assertEqual("avatar-generation", result["kind"])
            self.assertEqual(1, result["generated"])
            self.assertEqual(1, run_generation.call_args.args[0].test_mode)

    def test_web_error_rendering_escapes_error_message(self):
        page = render_home_page(error="<bad input>")

        self.assertIn("&lt;bad input&gt;", page)
        self.assertNotIn("<bad input>", page)

    def test_web_post_does_not_render_error_page_after_client_disconnect(self):
        handler = _GeneratorRequestHandler.__new__(_GeneratorRequestHandler)
        handler.path = "/background"
        handler._read_form = Mock(return_value={"source": ["input"]})
        handler._send_html = Mock(side_effect=BrokenPipeError)

        with patch("mv_artwork_creator.web.run_background_from_form", return_value={"kind": "background-removal"}):
            handler.do_POST()

        self.assertEqual(1, handler._send_html.call_count)


if __name__ == "__main__":
    unittest.main()
