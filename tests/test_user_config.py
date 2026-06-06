import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from mv_artwork_creator.paths import bundled_config_path
from mv_artwork_creator.user_config import (
    ensure_user_config,
    reset_user_config,
    resolve_config_path,
    seed_user_config,
    user_config_dir,
)


class UserConfigTests(unittest.TestCase):
    def test_seed_user_config_creates_missing_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            config_dir = Path(tmp) / "config"
            with patch.dict(os.environ, {"MVAC_CONFIG_DIR": str(config_dir)}, clear=True):
                written = seed_user_config(overwrite=False)
                self.assertEqual(4, len(written))
                for name in ("avatar_prompts.yaml", "scene_prompts.yaml", "messy_fy_prompts.yaml", "models.yaml"):
                    path = config_dir / name
                    self.assertTrue(path.exists())
                    self.assertEqual(
                        bundled_config_path(name).read_text(encoding="utf-8"),
                        path.read_text(encoding="utf-8"),
                    )

    def test_seed_user_config_skips_existing_without_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            config_dir = Path(tmp) / "config"
            config_dir.mkdir()
            custom = config_dir / "models.yaml"
            custom.write_text("custom: true\n", encoding="utf-8")
            with patch.dict(os.environ, {"MVAC_CONFIG_DIR": str(config_dir)}, clear=True):
                written = seed_user_config(overwrite=False)
                self.assertEqual(3, len(written))
                self.assertEqual("custom: true\n", custom.read_text(encoding="utf-8"))

    def test_reset_user_config_overwrites_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            config_dir = Path(tmp) / "config"
            config_dir.mkdir()
            custom = config_dir / "models.yaml"
            custom.write_text("custom: true\n", encoding="utf-8")
            with patch.dict(os.environ, {"MVAC_CONFIG_DIR": str(config_dir)}, clear=True):
                reset_user_config()
                self.assertEqual(
                    bundled_config_path("models.yaml").read_text(encoding="utf-8"),
                    custom.read_text(encoding="utf-8"),
                )

    def test_resolve_config_path_prefers_user_copy(self):
        with tempfile.TemporaryDirectory() as tmp:
            config_dir = Path(tmp) / "config"
            with patch.dict(os.environ, {"MVAC_CONFIG_DIR": str(config_dir)}, clear=True):
                ensure_user_config()
                resolved = resolve_config_path("scene_prompts.yaml")
                self.assertEqual(config_dir / "scene_prompts.yaml", resolved)

    def test_resolve_config_path_factory_ignores_user_copy(self):
        with tempfile.TemporaryDirectory() as tmp:
            config_dir = Path(tmp) / "config"
            with patch.dict(os.environ, {"MVAC_CONFIG_DIR": str(config_dir)}, clear=True):
                ensure_user_config()
                resolved = resolve_config_path("scene_prompts.yaml", factory=True)
                self.assertEqual(bundled_config_path("scene_prompts.yaml"), resolved)

    def test_env_override_takes_precedence_over_user_copy(self):
        with tempfile.TemporaryDirectory() as tmp:
            config_dir = Path(tmp) / "config"
            override = Path(tmp) / "custom_scene.yaml"
            override.write_text("override: true\n", encoding="utf-8")
            with patch.dict(
                os.environ,
                {"MVAC_CONFIG_DIR": str(config_dir), "MVAC_SCENE_PROMPTS": str(override)},
                clear=True,
            ):
                ensure_user_config()
                resolved = resolve_config_path("scene_prompts.yaml")
                self.assertEqual(override, resolved)

    def test_default_user_config_dir_is_config(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(Path("config"), user_config_dir())
