import tempfile
import unittest
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from PIL import Image

from mv_artwork_creator import web


def _png(path: Path) -> Path:
    buffer = BytesIO()
    Image.new("RGBA", (4, 4), (255, 0, 0, 255)).save(buffer, format="PNG")
    path.write_bytes(buffer.getvalue())
    return path


class WriteModeParsingTests(unittest.TestCase):
    def test_write_mode_falls_back_to_default_for_missing_or_unknown(self):
        self.assertEqual("skip", web._write_mode({}, "skip"))
        self.assertEqual("version", web._write_mode({"write_mode": ["bogus"]}, "version"))
        self.assertEqual("overwrite", web._write_mode({"write_mode": ["overwrite"]}, "skip"))


class NextFreeDirTests(unittest.TestCase):
    def test_returns_path_when_missing_or_empty(self):
        with tempfile.TemporaryDirectory() as tmp:
            missing = Path(tmp) / "avatars"
            self.assertEqual(missing, web._next_free_dir(missing))
            missing.mkdir()
            self.assertEqual(missing, web._next_free_dir(missing))

    def test_bumps_past_non_empty_dirs(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp) / "avatars"
            base.mkdir()
            (base / "x.png").write_bytes(b"x")
            self.assertEqual(base.with_name("avatars-2"), web._next_free_dir(base))
            sibling = base.with_name("avatars-2")
            sibling.mkdir()
            (sibling / "y.png").write_bytes(b"y")
            self.assertEqual(base.with_name("avatars-3"), web._next_free_dir(base))


class NextFreeFilenameConfigTests(unittest.TestCase):
    """The config is bumped to the next free `-N` based on the plan it would build."""

    def _build_plan(self, existing: set[str]):
        def build(config):
            name = config.filename or "blueprint"
            return SimpleNamespace(output_path=_FakePath(f"{name}.png", existing))

        return build

    def test_keeps_config_when_target_free(self):
        config = SimpleNamespace(filename=None, with_updates=lambda **k: None)
        result = web._next_free_filename_config(config, self._build_plan(existing=set()))
        self.assertIs(config, result)

    def test_bumps_until_free(self):
        existing = {"blueprint.png", "blueprint-2.png"}

        def with_updates(**kwargs):
            return SimpleNamespace(filename=kwargs["filename"], with_updates=with_updates)

        config = SimpleNamespace(filename=None, with_updates=with_updates)
        result = web._next_free_filename_config(config, self._build_plan(existing))
        self.assertEqual("blueprint-3", result.filename)


class _FakePath:
    def __init__(self, name: str, existing: set[str]):
        self.name = name
        self.stem = name.rsplit(".", 1)[0]
        self._existing = existing

    def exists(self) -> bool:
        return self.name in self._existing


class MessyFyWriteModeIntegrationTests(unittest.TestCase):
    def _form(self, tmp: Path, source: Path, mode: str) -> dict[str, list[str]]:
        return {
            "source_image": [str(source)],
            "output_dir": [str(tmp / "out")],
            "filename": [""],
            "hint": [""],
            "write_mode": [mode],
            "dry_run": ["1"],
        }

    def test_version_bumps_when_existing_overwrite_and_skip_keep_base(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            source = _png(tmp_path / "blueprint02.png")
            out = tmp_path / "out"
            out.mkdir()

            first = web.run_messy_fy_dry_run_from_form(self._form(tmp_path, source, "version"))
            self.assertEqual("blueprint02.png", Path(first["output_path"]).name)

            Path(first["output_path"]).write_bytes(b"x")
            second = web.run_messy_fy_dry_run_from_form(self._form(tmp_path, source, "version"))
            self.assertEqual("blueprint02-2.png", Path(second["output_path"]).name)

            skip = web.run_messy_fy_dry_run_from_form(self._form(tmp_path, source, "skip"))
            self.assertEqual("blueprint02.png", Path(skip["output_path"]).name)

            overwrite = web.run_messy_fy_dry_run_from_form(self._form(tmp_path, source, "overwrite"))
            self.assertEqual("blueprint02.png", Path(overwrite["output_path"]).name)


class AvatarWriteModeIntegrationTests(unittest.TestCase):
    def test_version_bumps_output_dir_skip_keeps_it(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            source = _png(tmp_path / "avatar.png")
            avatars = tmp_path / "avatars"
            avatars.mkdir()
            (avatars / "front.png").write_bytes(b"x")

            base = {"source_image": [str(source)], "output_dir": [str(avatars)], "dry_run": ["1"]}

            versioned = web.run_avatar_dry_run_from_form({**base, "write_mode": ["version"]})
            self.assertEqual("avatars-2", Path(versioned["output_dir"]).name)

            skipped = web.run_avatar_dry_run_from_form({**base, "write_mode": ["skip"]})
            self.assertEqual("avatars", Path(skipped["output_dir"]).name)


class BackgroundWriteModeIntegrationTests(unittest.TestCase):
    def _summary(self):
        return SimpleNamespace(planned=1, converted=1, skipped=0, failed=0)

    def test_modes_map_to_overwrite_flag_and_output_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            source = _png(tmp_path / "pic.png")
            out = tmp_path / "out"
            out.mkdir()
            (out / "existing.png").write_bytes(b"x")

            def form(mode):
                return {
                    "source": [str(source)],
                    "output_dir": [str(out)],
                    "method": ["rembg"],
                    "write_mode": [mode],
                }

            with patch("mv_artwork_creator.web.remove_backgrounds", return_value=self._summary()) as mock:
                web.run_background_from_form(form("skip"))
                self.assertEqual(out, mock.call_args.args[1])
                self.assertFalse(mock.call_args.kwargs["overwrite"])

                web.run_background_from_form(form("overwrite"))
                self.assertTrue(mock.call_args.kwargs["overwrite"])

                web.run_background_from_form(form("version"))
                self.assertEqual(out.with_name("out-2"), mock.call_args.args[1])
                self.assertFalse(mock.call_args.kwargs["overwrite"])


if __name__ == "__main__":
    unittest.main()
