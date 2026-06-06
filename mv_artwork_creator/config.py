from __future__ import annotations

import os
from dataclasses import dataclass, field, replace
from pathlib import Path

from .user_config import default_avatar_prompt_library


DEFAULT_MODEL = "bytedance-seed/seedream-4.5"
DEFAULT_OUTPUT_DIR = Path("output/avatars")


def load_env_file(path: Path = Path(".env"), *, override: bool = False) -> dict[str, str]:
    if not path.exists():
        return {}

    loaded: dict[str, str] = {}
    for line_number, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :].strip()
        if "=" not in line:
            raise ValueError(f"Invalid .env line {line_number}: expected KEY=VALUE")

        key, value = line.split("=", 1)
        key = key.strip()
        value = _parse_env_value(value.strip())
        if not key:
            raise ValueError(f"Invalid .env line {line_number}: missing key")
        if override or key not in os.environ:
            os.environ[key] = value
        loaded[key] = value
    return loaded


def _parse_env_value(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        value = value[1:-1]
    return value


def default_model() -> str:
    from .models import GenerationTask, default_model_for_task

    return default_model_for_task(GenerationTask.AVATAR)


def default_prompt_library(*, factory: bool = False) -> Path:
    return default_avatar_prompt_library(factory=factory)


def default_output_dir() -> Path:
    return Path(os.environ.get("MVAC_AVATAR_OUTPUT", str(DEFAULT_OUTPUT_DIR)))


@dataclass(frozen=True)
class GenerationConfig:
    source_image: Path
    output_dir: Path = DEFAULT_OUTPUT_DIR
    prompt_library: Path = field(default_factory=default_avatar_prompt_library)
    model: str = DEFAULT_MODEL
    api_key: str | None = None
    presets: list[str] | None = None
    test_mode: bool = False
    test_preset: str | None = None
    dry_run: bool = False
    regenerate: bool = False
    continue_on_error: bool = True
    concurrency: int = 1
    retry_count: int = 0

    def resolved_api_key(self) -> str | None:
        return self.api_key or os.environ.get("OPENROUTER_API_KEY")

    def with_updates(self, **updates: object) -> "GenerationConfig":
        return replace(self, **updates)
