from __future__ import annotations

from importlib.resources import files
from pathlib import Path


def bundled_config_path(name: str) -> Path:
    return Path(str(files("mv_artwork_creator.resources").joinpath(name)))
