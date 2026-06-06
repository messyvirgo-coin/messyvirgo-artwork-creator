from __future__ import annotations

import os
import shutil
from pathlib import Path

from .paths import bundled_config_path

CONFIG_FILENAMES: tuple[str, ...] = (
    "avatar_prompts.yaml",
    "scene_prompts.yaml",
    "messy_fy_prompts.yaml",
    "models.yaml",
)

_ENV_CONFIG_DIR = "MVAC_CONFIG_DIR"
_ENV_OVERRIDES: dict[str, str] = {
    "avatar_prompts.yaml": "MVAC_AVATAR_PROMPTS",
    "scene_prompts.yaml": "MVAC_SCENE_PROMPTS",
    "messy_fy_prompts.yaml": "MVAC_MESSY_FY_PROMPTS",
    "models.yaml": "MVAC_MODELS",
}


def user_config_dir() -> Path:
    return Path(os.environ.get(_ENV_CONFIG_DIR, "config"))


def resolve_config_path(name: str, *, factory: bool = False) -> Path:
    if factory:
        return bundled_config_path(name)

    env_key = _ENV_OVERRIDES.get(name)
    if env_key:
        override = os.environ.get(env_key)
        if override and override.strip():
            return Path(override.strip())

    user_path = user_config_dir() / name
    if user_path.exists():
        return user_path

    return bundled_config_path(name)


def default_avatar_prompt_library(*, factory: bool = False) -> Path:
    return resolve_config_path("avatar_prompts.yaml", factory=factory)


def default_scene_prompt_library(*, factory: bool = False) -> Path:
    return resolve_config_path("scene_prompts.yaml", factory=factory)


def default_messy_fy_prompt_library(*, factory: bool = False) -> Path:
    return resolve_config_path("messy_fy_prompts.yaml", factory=factory)


def default_models_path(*, factory: bool = False) -> Path:
    return resolve_config_path("models.yaml", factory=factory)


def seed_user_config(*, overwrite: bool = False) -> list[Path]:
    """Copy bundled YAML defaults into the user config directory."""
    config_dir = user_config_dir()
    config_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for name in CONFIG_FILENAMES:
        destination = config_dir / name
        if destination.exists() and not overwrite:
            continue
        shutil.copy2(bundled_config_path(name), destination)
        written.append(destination)
    return written


def ensure_user_config() -> list[Path]:
    return seed_user_config(overwrite=False)


def reset_user_config() -> list[Path]:
    return seed_user_config(overwrite=True)
