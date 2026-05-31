from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True)
class ScenePromptLibrary:
    system_prompt: str
    negative_prompt: str

    def compose_prompt(self, *, setting: str, action: str) -> str:
        setting = setting.strip()
        action = action.strip()
        if not setting:
            raise ValueError("Scene setting must not be empty")
        if not action:
            raise ValueError("Scene action must not be empty")

        try:
            return self.system_prompt.format(setting=setting, action=action).strip()
        except KeyError as exc:
            raise ValueError(f"Scene prompt references unknown placeholder: {exc}") from exc


def load_scene_prompt_library(path: Path) -> ScenePromptLibrary:
    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle)

    if not isinstance(data, dict):
        raise ValueError("Scene prompt YAML must contain a mapping")

    system_prompt = _required_text(data, "system_prompt")
    negative_prompt = _required_text(data, "negative_prompt")
    return ScenePromptLibrary(system_prompt=system_prompt, negative_prompt=negative_prompt)


def _required_text(data: dict[str, Any], key: str) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Scene prompt library must define {key}")
    return value
