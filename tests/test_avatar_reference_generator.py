import base64
import json
import os
import tempfile
import unittest
from contextlib import redirect_stdout
from io import BytesIO, StringIO
from pathlib import Path
from unittest.mock import patch

from PIL import Image

from avatar_reference_generator.background import _strip_near_white_remnants, remove_backgrounds
from avatar_reference_generator.sharpen import sharpen_image
from avatar_reference_generator.config import GenerationConfig, load_env_file
from avatar_reference_generator.cli import main
from avatar_reference_generator.executor import run_generation
from avatar_reference_generator.openrouter import OpenRouterClient
from avatar_reference_generator.planner import create_generation_plan
from avatar_reference_generator.prompts import load_prompt_library
from avatar_reference_generator.validation import validate_png_alpha


PNG_RGBA_1X1 = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAFgwJ/lY8pngAAAABJRU5ErkJggg=="
)
PNG_RGB_1X1 = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAIAAACQd1PeAAAADUlEQVR42mP8z8BQDwAFgwJ/lY8pngAAAABJRU5ErkJggg=="
)
PNG_PALETTE_TRNS_1X1 = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAMAAAAoyzS7AAAABlBMVEUAAAAAAP8KDwstAAAAAXRSTlMAQObYZgAAAApJREFUeJxjYAAAAAIAAc/INeUAAAAASUVORK5CYII="
)


def make_jpeg_bytes() -> bytes:
    buffer = BytesIO()
    Image.new("RGB", (2, 2), "white").save(buffer, format="JPEG")
    return buffer.getvalue()


def make_png_bytes() -> bytes:
    buffer = BytesIO()
    Image.new("RGBA", (2, 2), (255, 255, 255, 0)).save(buffer, format="PNG")
    return buffer.getvalue()


class FakeClient:
    def __init__(self):
        self.requests = []

    def generate_image(self, request):
        self.requests.append(request)
        return {
            "image_bytes": make_png_bytes(),
            "mime_type": "image/png",
            "extension": ".png",
            "response_id": f"resp-{len(self.requests)}",
            "raw": {"id": f"resp-{len(self.requests)}"},
        }


class FlakyClient:
    def __init__(self):
        self.requests = []

    def generate_image(self, request):
        self.requests.append(request)
        if len(self.requests) == 1:
            raise RuntimeError("temporary failure")
        return {"image_bytes": make_png_bytes(), "mime_type": "image/png", "extension": ".png", "response_id": "resp-ok", "raw": {}}


class AvatarReferenceGeneratorTests(unittest.TestCase):
    def test_load_env_file_sets_openrouter_key_without_overriding_existing_values(self):
        previous_key = os.environ.get("OPENROUTER_API_KEY")
        previous_model = os.environ.get("AVATAR_REFERENCE_MODEL")
        try:
            os.environ["OPENROUTER_API_KEY"] = "already-exported"
            os.environ.pop("AVATAR_REFERENCE_MODEL", None)
            with tempfile.TemporaryDirectory() as tmp:
                env_file = Path(tmp) / ".env"
                env_file.write_text(
                    'OPENROUTER_API_KEY="from-file"\nexport AVATAR_REFERENCE_MODEL=custom/model\n',
                    encoding="utf-8",
                )

                loaded = load_env_file(env_file)

            self.assertEqual("from-file", loaded["OPENROUTER_API_KEY"])
            self.assertEqual("already-exported", os.environ["OPENROUTER_API_KEY"])
            self.assertEqual("custom/model", os.environ["AVATAR_REFERENCE_MODEL"])
        finally:
            if previous_key is None:
                os.environ.pop("OPENROUTER_API_KEY", None)
            else:
                os.environ["OPENROUTER_API_KEY"] = previous_key
            if previous_model is None:
                os.environ.pop("AVATAR_REFERENCE_MODEL", None)
            else:
                os.environ["AVATAR_REFERENCE_MODEL"] = previous_model

    def test_prompt_library_loads_and_composes_prompt(self):
        library = load_prompt_library(Path("config/avatar_prompts.yaml"))

        prompt = library.compose_prompt("front_45_left", "half_body")

        self.assertIn("strict character reference", prompt)
        self.assertIn("character's left", prompt)
        self.assertIn("hip line", prompt)
        self.assertIn("Do not redesign", library.negative_prompt)

    def test_prompt_library_describes_messy_as_elegant_allocator_with_long_trousers(self):
        library = load_prompt_library(Path("config/avatar_prompts.yaml"))

        full_body_prompt = library.compose_prompt("front", "full_body")

        self.assertIn("elegant crypto finance funds allocator", full_body_prompt)
        self.assertIn("long trousers", full_body_prompt)
        self.assertIn("must not add props", full_body_prompt)
        self.assertIn("exactly one character", full_body_prompt)
        self.assertIn("mini skirt", library.negative_prompt)
        self.assertIn("not replace her long trousers with a mini skirt", library.negative_prompt)
        self.assertIn("tablet", library.negative_prompt)
        self.assertIn("new accessories", library.negative_prompt)

    def test_missing_prompt_fragment_is_rejected(self):
        library = load_prompt_library(Path("config/avatar_prompts.yaml"))

        with self.assertRaisesRegex(ValueError, "Missing angle prompt"):
            library.compose_prompt("not_an_angle", "portrait")

    def test_missing_negative_prompt_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            prompt_file = Path(tmp) / "prompts.yaml"
            prompt_file.write_text(
                "base_prompt: base\nangles:\n  front:\n    prompt: front\nshots:\n  portrait:\n    prompt: portrait\n",
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "negative_prompt"):
                load_prompt_library(prompt_file)

    def test_default_plan_contains_expected_reference_matrix(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "avatar.png"
            source.write_bytes(PNG_RGBA_1X1)
            config = GenerationConfig(source_image=source, output_dir=Path(tmp) / "out")
            library = load_prompt_library(Path("config/avatar_prompts.yaml"))

            plan = create_generation_plan(config, library)

            self.assertEqual(21, len(plan.items))
            self.assertEqual(("front", "portrait"), (plan.items[0].angle_id, plan.items[0].shot_id))
            self.assertEqual(("back", "full_body"), (plan.items[-1].angle_id, plan.items[-1].shot_id))

    def test_custom_plan_uses_only_selected_presets(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "avatar.png"
            source.write_bytes(PNG_RGBA_1X1)
            config = GenerationConfig(
                source_image=source,
                output_dir=Path(tmp) / "out",
                presets=["front:portrait", "left_side:full_body"],
            )
            library = load_prompt_library(Path("config/avatar_prompts.yaml"))

            plan = create_generation_plan(config, library)

            self.assertEqual(
                [("front", "portrait"), ("left_side", "full_body")],
                [(item.angle_id, item.shot_id) for item in plan.items],
            )

    def test_test_mode_limits_plan_to_one_default_or_selected_item(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "avatar.png"
            source.write_bytes(PNG_RGBA_1X1)
            library = load_prompt_library(Path("config/avatar_prompts.yaml"))

            default_plan = create_generation_plan(
                GenerationConfig(source_image=source, output_dir=Path(tmp) / "out", test_mode=True),
                library,
            )
            selected_plan = create_generation_plan(
                GenerationConfig(
                    source_image=source,
                    output_dir=Path(tmp) / "out",
                    test_mode=True,
                    test_preset="right_side:full_body",
                ),
                library,
            )

            self.assertEqual([("front", "portrait")], [(i.angle_id, i.shot_id) for i in default_plan.items])
            self.assertEqual(
                [("right_side", "full_body")],
                [(i.angle_id, i.shot_id) for i in selected_plan.items],
            )

    def test_png_validation_rejects_non_png_and_png_without_alpha(self):
        with tempfile.TemporaryDirectory() as tmp:
            rgba = Path(tmp) / "rgba.png"
            rgb = Path(tmp) / "rgb.png"
            palette = Path(tmp) / "palette.png"
            text = Path(tmp) / "avatar.txt"
            rgba.write_bytes(PNG_RGBA_1X1)
            rgb.write_bytes(PNG_RGB_1X1)
            palette.write_bytes(PNG_PALETTE_TRNS_1X1)
            text.write_text("not png")

            validate_png_alpha(rgba)
            validate_png_alpha(palette)
            with self.assertRaisesRegex(ValueError, "transparent PNG"):
                validate_png_alpha(text)
            with self.assertRaisesRegex(ValueError, "alpha channel"):
                validate_png_alpha(rgb)

    def test_png_validation_rejects_missing_file_with_clear_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError, "does not exist"):
                validate_png_alpha(Path(tmp) / "missing.png")

    def test_openrouter_request_includes_image_model_prompt_and_negative_prompt(self):
        client = OpenRouterClient(api_key="test-key")
        request = client.build_payload(
            model="bytedance-seed/seedream-4.5",
            prompt="base plus angle plus shot",
            negative_prompt="avoid changes",
            source_image_bytes=PNG_RGBA_1X1,
            source_mime_type="image/png",
        )

        self.assertEqual("bytedance-seed/seedream-4.5", request["model"])
        self.assertEqual(["image"], request["modalities"])
        content = request["messages"][0]["content"]
        self.assertEqual("text", content[0]["type"])
        self.assertIn("base plus angle plus shot", content[0]["text"])
        self.assertIn("avoid changes", content[0]["text"])
        self.assertEqual("image_url", content[1]["type"])
        self.assertTrue(content[1]["image_url"]["url"].startswith("data:image/png;base64,"))

    def test_openrouter_accepts_supported_non_png_image_response(self):
        client = OpenRouterClient(api_key="test-key")

        response = client.parse_response(
            {
                "choices": [
                    {
                        "message": {
                            "images": [
                                {"image_url": {"url": "data:image/jpeg;base64,AAAA"}},
                            ]
                        }
                    }
                ]
            }
        )

        self.assertEqual("image/jpeg", response["mime_type"])
        self.assertEqual(".jpg", response["extension"])

    def test_generation_writes_metadata_resumes_and_regenerates(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "avatar.png"
            output = Path(tmp) / "out"
            source.write_bytes(PNG_RGBA_1X1)
            library = load_prompt_library(Path("config/avatar_prompts.yaml"))
            config = GenerationConfig(
                source_image=source,
                output_dir=output,
                test_mode=True,
                prompt_library=Path("config/avatar_prompts.yaml"),
            )

            client = FakeClient()
            first = run_generation(config, library, client)
            second = run_generation(config, library, client)
            third = run_generation(config.with_updates(regenerate=True), library, client)

            metadata_path = output / "front__portrait.json"
            metadata = json.loads(metadata_path.read_text())

            self.assertEqual(1, first.generated)
            self.assertEqual(0, first.skipped)
            self.assertEqual(0, second.generated)
            self.assertEqual(1, second.skipped)
            self.assertEqual(1, third.generated)
            self.assertEqual(2, len(client.requests))
            self.assertEqual("succeeded", metadata["status"])
            self.assertEqual("front", metadata["angle_id"])
            self.assertEqual("portrait", metadata["shot_id"])
            self.assertEqual(str(output / "front__portrait.png"), metadata["output_path"])
            self.assertIn("prompt", metadata)

    def test_generation_normalizes_non_png_response_to_png(self):
        class JpegClient:
            def generate_image(self, request):
                return {"image_bytes": make_jpeg_bytes(), "mime_type": "image/jpeg", "extension": ".jpg", "response_id": "jpeg", "raw": {}}

        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "avatar.png"
            output = Path(tmp) / "out"
            source.write_bytes(PNG_RGBA_1X1)
            library = load_prompt_library(Path("config/avatar_prompts.yaml"))

            run_generation(GenerationConfig(source_image=source, output_dir=output, test_mode=True), library, JpegClient())
            metadata = json.loads((output / "front__portrait.json").read_text())

            self.assertTrue((output / "front__portrait.png").exists())
            self.assertEqual(str(output / "front__portrait.png"), metadata["output_path"])
            self.assertEqual("image/jpeg", metadata["provider_mime_type"])
            self.assertEqual("image/png", metadata["mime_type"])

    def test_resume_regenerates_when_source_or_prompt_changes(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "avatar.png"
            output = Path(tmp) / "out"
            source.write_bytes(PNG_RGBA_1X1)
            library = load_prompt_library(Path("config/avatar_prompts.yaml"))
            config = GenerationConfig(source_image=source, output_dir=output, test_mode=True)
            client = FakeClient()

            run_generation(config, library, client)
            source.write_bytes(PNG_PALETTE_TRNS_1X1)
            run_generation(config, library, client)
            changed_library = library.__class__(
                base_prompt=library.base_prompt + "\nPreserve exact proportions.",
                negative_prompt=library.negative_prompt,
                angles=library.angles,
                shots=library.shots,
                composition=library.composition,
            )
            run_generation(config, changed_library, client)

            self.assertEqual(3, len(client.requests))

    def test_generation_retries_provider_failures(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "avatar.png"
            output = Path(tmp) / "out"
            source.write_bytes(PNG_RGBA_1X1)
            library = load_prompt_library(Path("config/avatar_prompts.yaml"))
            config = GenerationConfig(
                source_image=source,
                output_dir=output,
                test_mode=True,
                retry_count=1,
            )
            client = FlakyClient()

            summary = run_generation(config, library, client)

            self.assertEqual(1, summary.generated)
            self.assertEqual(0, summary.failed)
            self.assertEqual(2, len(client.requests))

    def test_negative_retry_count_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "avatar.png"
            source.write_bytes(PNG_RGBA_1X1)
            library = load_prompt_library(Path("config/avatar_prompts.yaml"))
            config = GenerationConfig(source_image=source, output_dir=Path(tmp) / "out", test_mode=True, retry_count=-1)

            with self.assertRaisesRegex(ValueError, "retry_count"):
                run_generation(config, library, FakeClient())

    def test_cli_rejects_test_preset_without_test_mode(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "avatar.png"
            source.write_bytes(PNG_RGBA_1X1)

            with self.assertRaises(SystemExit) as raised:
                main([str(source), "--dry-run", "--test-preset", "front:portrait"])

            self.assertNotEqual(0, raised.exception.code)

    def test_sharpen_image_preserves_alpha_and_changes_rgb(self):
        image = Image.new("RGBA", (8, 8), (240, 240, 240, 255))
        image.putpixel((4, 4), (20, 40, 60, 255))
        sharpened = sharpen_image(image)
        self.assertEqual(255, sharpened.getpixel((4, 4))[3])
        self.assertNotEqual(image.getpixel((4, 4))[:3], sharpened.getpixel((4, 4))[:3])

    def test_sharpen_cli_writes_default_sibling_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            source_dir = Path(tmp) / "raw"
            source_dir.mkdir()
            Image.new("RGB", (4, 4), (200, 200, 200)).save(source_dir / "sample.png")

            with redirect_stdout(StringIO()):
                exit_code = main(["sharpen", "--input-dir", str(source_dir)])

            self.assertEqual(0, exit_code)
            self.assertTrue((Path(tmp) / "raw-sharpened" / "sample.png").exists())

    def test_strip_near_white_remnants_removes_enclosed_white(self):
        image = Image.new("RGBA", (6, 6), (0, 0, 0, 0))
        for x in range(6):
            image.putpixel((x, 0), (20, 30, 40, 255))
            image.putpixel((x, 5), (20, 30, 40, 255))
        for y in range(6):
            image.putpixel((0, y), (20, 30, 40, 255))
            image.putpixel((5, y), (20, 30, 40, 255))
        image.putpixel((3, 3), (255, 255, 255, 255))
        image.putpixel((2, 2), (250, 249, 248, 200))
        image.putpixel((1, 1), (180, 120, 90, 255))

        _strip_near_white_remnants(image, threshold=242)

        self.assertEqual(0, image.getpixel((3, 3))[3])
        self.assertEqual(0, image.getpixel((2, 2))[3])
        self.assertGreater(image.getpixel((1, 1))[3], 0)

    def test_remove_backgrounds_converts_jpg_to_transparent_png(self):
        with tempfile.TemporaryDirectory() as tmp:
            source_dir = Path(tmp) / "jpgs"
            output_dir = Path(tmp) / "pngs"
            source_dir.mkdir()
            jpg_path = source_dir / "front__portrait.jpg"
            image = Image.new("RGB", (8, 8), "white")
            for x in range(2, 6):
                for y in range(2, 6):
                    image.putpixel((x, y), (10, 20, 30))
            image.save(jpg_path, quality=95)

            summary = remove_backgrounds(
                source_dir,
                output_dir,
                method="flood",
                tolerance=30,
                pre_sharpen=False,
            )
            output_path = output_dir / "front__portrait.png"
            result = Image.open(output_path).convert("RGBA")

            self.assertEqual(1, summary.converted)
            self.assertEqual(0, summary.failed)
            self.assertEqual(0, result.getpixel((0, 0))[3])
            self.assertGreater(result.getpixel((3, 3))[3], 200)

    def test_remove_background_cli_converts_input_dir_to_default_sibling_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            source_dir = Path(tmp) / "jpgs"
            source_dir.mkdir()
            Image.new("RGB", (3, 3), "white").save(source_dir / "empty.jpg")

            with redirect_stdout(StringIO()):
                exit_code = main(["remove-background", "--input-dir", str(source_dir), "--method", "flood"])

            self.assertEqual(0, exit_code)
            self.assertTrue((Path(tmp) / "jpgs-transparent" / "empty.png").exists())

    def test_remove_background_module_entry_dispatches_from_sys_argv(self):
        with tempfile.TemporaryDirectory() as tmp:
            source_dir = Path(tmp) / "jpgs"
            source_dir.mkdir()
            Image.new("RGB", (3, 3), "white").save(source_dir / "empty.jpg")

            with patch(
                "sys.argv",
                ["avatar_reference_generator", "remove-background", "--input-dir", str(source_dir), "--method", "flood"],
            ):
                with redirect_stdout(StringIO()):
                    exit_code = main()

            self.assertEqual(0, exit_code)
            self.assertTrue((Path(tmp) / "jpgs-transparent" / "empty.png").exists())

    def test_remove_background_cli_rejects_multiple_input_shapes(self):
        with tempfile.TemporaryDirectory() as tmp:
            source_dir = Path(tmp) / "jpgs"
            source_dir.mkdir()

            with self.assertRaises(SystemExit):
                main(["remove-background", str(source_dir), "--input-dir", str(source_dir)])


if __name__ == "__main__":
    unittest.main()
