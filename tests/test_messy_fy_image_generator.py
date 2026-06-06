import json
import os
import tempfile
import unittest
from contextlib import redirect_stdout
from io import BytesIO, StringIO
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from PIL import Image

from mv_artwork_creator.cli import main
from mv_artwork_creator.images import load_image_for_provider
from mv_artwork_creator.models import (
    GenerationTask,
    load_model_registry,
    resolve_model,
    resolve_model_name,
)
from mv_artwork_creator.messy_fy_executor import (
    MessyFyGenerationConfig,
    create_messy_fy_plan,
    run_messy_fy_generation,
)
from mv_artwork_creator.messy_fy_prompts import load_messy_fy_prompt_library
from mv_artwork_creator.paths import bundled_config_path


def make_png_bytes() -> bytes:
    buffer = BytesIO()
    Image.new("RGBA", (2, 2), (255, 255, 255, 0)).save(buffer, format="PNG")
    return buffer.getvalue()


def make_jpeg_bytes() -> bytes:
    buffer = BytesIO()
    Image.new("RGB", (2, 2), "white").save(buffer, format="JPEG")
    return buffer.getvalue()


class FakeMessyFyClient:
    def __init__(self):
        self.requests = []

    def generate_image(self, request):
        self.requests.append(request)
        return {
            "image_bytes": make_png_bytes(),
            "mime_type": "image/png",
            "extension": ".png",
            "response_id": f"messy-fy-{len(self.requests)}",
            "raw": {"id": f"messy-fy-{len(self.requests)}"},
        }


class ModelRegistryTests(unittest.TestCase):
    def test_resolve_model_alias_and_task_defaults(self):
        registry = load_model_registry(Path("mv_artwork_creator/resources/models.yaml"))
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(
                "bytedance-seed/seedream-4.5",
                resolve_model("seedream", GenerationTask.MESSY_FY, registry=registry),
            )
            self.assertEqual(
                "bytedance-seed/seedream-4.5",
                resolve_model(None, GenerationTask.SCENE, registry=registry),
            )
            self.assertEqual(
                "google/gemini-3.1-flash-image-preview",
                resolve_model(None, GenerationTask.MESSY_FY, registry=registry),
            )
        self.assertEqual("custom/provider", resolve_model_name("custom/provider", registry=registry))

    def test_resolve_model_uses_task_specific_env(self):
        registry = load_model_registry(Path("mv_artwork_creator/resources/models.yaml"))
        with patch.dict(
            os.environ,
            {
                "MVAC_SCENE_MODEL": "scene/model",
                "MVAC_AVATAR_MODEL": "avatar/model",
            },
            clear=True,
        ):
            self.assertEqual("scene/model", resolve_model(None, GenerationTask.SCENE, registry=registry))
            self.assertEqual("avatar/model", resolve_model(None, GenerationTask.AVATAR, registry=registry))

    def test_resolve_model_uses_messy_fy_env(self):
        registry = load_model_registry(Path("mv_artwork_creator/resources/models.yaml"))
        with patch.dict(os.environ, {"MVAC_MESSY_FY_MODEL": "messy/model"}, clear=True):
            self.assertEqual("messy/model", resolve_model(None, GenerationTask.MESSY_FY, registry=registry))


class MessyFyImageGeneratorTests(unittest.TestCase):
    def test_messy_fy_prompt_library_composes_brand_prompt_with_optional_hint(self):
        library = load_messy_fy_prompt_library(Path("mv_artwork_creator/resources/messy_fy_prompts.yaml"))

        prompt = library.compose_prompt(hint="keep the confident standing pose")
        no_hint = library.compose_prompt()

        self.assertIn("Repaint the attached reference image", prompt)
        self.assertIn("Messy Virgo brand visual style", prompt)
        self.assertIn("stylistic repaint only", prompt)
        self.assertIn("preserve the source intent and hierarchy", prompt)
        self.assertIn("preserve the original image structure closely", prompt)
        self.assertIn("replace source fonts", prompt)
        self.assertIn("primary neon pink accent", prompt)
        self.assertIn("amber only as a restrained secondary accent", prompt)
        self.assertIn("dark glassmorphism panels", prompt)
        self.assertIn("Restyle source background colors", prompt)
        self.assertIn("subtle blue, pink, and violet neon accents", prompt)
        self.assertIn("Avoid monospaced, typewriter, blueprint", prompt)
        self.assertIn("Do not insert Messy the character", prompt)
        self.assertIn("Additional guidance: keep the confident standing pose", prompt)
        self.assertNotIn("Additional guidance:", no_hint)
        self.assertIn("Changing, removing, misspelling", library.negative_prompt)

    def test_load_image_for_provider_accepts_png_and_jpeg(self):
        with tempfile.TemporaryDirectory() as tmp:
            png_path = Path(tmp) / "photo.png"
            jpeg_path = Path(tmp) / "photo.jpg"
            png_path.write_bytes(make_png_bytes())
            jpeg_path.write_bytes(make_jpeg_bytes())

            _, png_mime = load_image_for_provider(png_path)
            _, jpeg_mime = load_image_for_provider(jpeg_path)

            self.assertEqual("image/png", png_mime)
            self.assertEqual("image/jpeg", jpeg_mime)

    def test_load_image_for_provider_rejects_unsupported_suffix(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "photo.gif"
            path.write_bytes(make_png_bytes())
            with self.assertRaisesRegex(ValueError, "must be one of"):
                load_image_for_provider(path)

    def test_messy_fy_generation_writes_metadata_resumes_and_regenerates(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "photo.jpg"
            output = Path(tmp) / "out"
            source.write_bytes(make_jpeg_bytes())
            library = load_messy_fy_prompt_library(Path("mv_artwork_creator/resources/messy_fy_prompts.yaml"))
            config = MessyFyGenerationConfig(
                source_image=source,
                output_dir=output,
                model="custom/messy-model",
                hint="keep the smile",
                filename="styled",
                prompt_library=Path("mv_artwork_creator/resources/messy_fy_prompts.yaml"),
            )

            client = FakeMessyFyClient()
            first = run_messy_fy_generation(config, library, client)
            second = run_messy_fy_generation(config, library, client)
            third = run_messy_fy_generation(config.with_updates(regenerate=True), library, client)

            metadata = json.loads((output / "styled.json").read_text())
            first_request = client.requests[0]

            self.assertEqual(1, first.generated)
            self.assertEqual(1, second.skipped)
            self.assertEqual(1, third.generated)
            self.assertEqual(2, len(client.requests))
            self.assertEqual("custom/messy-model", first_request.model)
            self.assertEqual("image/jpeg", first_request.source_mime_type)
            self.assertIn("keep the smile", first_request.prompt)
            self.assertEqual("succeeded", metadata["status"])
            self.assertEqual("image/jpeg", metadata["source_mime_type"])

    def test_messy_fy_cli_dry_run_prints_plan_without_provider_request(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "photo.jpg"
            source.write_bytes(make_jpeg_bytes())
            stdout = StringIO()

            with redirect_stdout(stdout):
                exit_code = main(
                    [
                        "messy-fy",
                        str(source),
                        "--hint",
                        "keep the pose",
                        "--output-dir",
                        str(Path(tmp) / "out"),
                        "--dry-run",
                    ]
                )

            payload = json.loads(stdout.getvalue())
            self.assertEqual(0, exit_code)
            self.assertEqual("keep the pose", payload["hint"])
            self.assertEqual("image/jpeg", payload["source_mime_type"])
            self.assertTrue(payload["openrouter_request"]["reference_image_attached"])

    def test_messy_fy_cli_generation_uses_client_and_prints_summary(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "photo.jpg"
            source.write_bytes(make_jpeg_bytes())
            stdout = StringIO()
            summary = SimpleNamespace(planned=1, generated=1, skipped=0, failed=0)

            with patch("mv_artwork_creator.cli.OpenRouterClient") as client_class:
                with patch("mv_artwork_creator.cli.run_messy_fy_generation", return_value=summary) as run_messy_fy:
                    with redirect_stdout(stdout):
                        exit_code = main(
                            [
                                "messy-fy",
                                str(source),
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
            self.assertEqual(client_class.return_value, run_messy_fy.call_args.args[2])

    def test_messy_fy_plan_uses_resolved_model_alias(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "photo.png"
            source.write_bytes(make_png_bytes())
            library = load_messy_fy_prompt_library(Path("mv_artwork_creator/resources/messy_fy_prompts.yaml"))
            config = MessyFyGenerationConfig(
                source_image=source,
                output_dir=Path(tmp) / "out",
                model=resolve_model("seedream", GenerationTask.MESSY_FY),
            )
            plan = create_messy_fy_plan(config, library)
            self.assertEqual("bytedance-seed/seedream-4.5", plan.model)

    def test_bundled_config_paths_resolve_inside_package(self):
        from mv_artwork_creator.paths import bundled_config_path

        self.assertTrue(bundled_config_path("models.yaml").exists())
        self.assertTrue(bundled_config_path("scene_prompts.yaml").exists())
        self.assertTrue(bundled_config_path("messy_fy_prompts.yaml").exists())
        self.assertTrue(bundled_config_path("avatar_prompts.yaml").exists())


if __name__ == "__main__":
    unittest.main()
