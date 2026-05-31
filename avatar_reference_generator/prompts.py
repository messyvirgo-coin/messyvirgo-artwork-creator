from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True)
class PromptLibrary:
    base_prompt: str
    negative_prompt: str
    angles: dict[str, str]
    shots: dict[str, str]
    composition: str = ""

    def compose_prompt(self, angle_id: str, shot_id: str) -> str:
        if angle_id not in self.angles:
            raise ValueError(f"Missing angle prompt fragment: {angle_id}")
        if shot_id not in self.shots:
            raise ValueError(f"Missing shot prompt fragment: {shot_id}")

        parts = [
            self.base_prompt.strip(),
            self.angles[angle_id].strip(),
            self.shots[shot_id].strip(),
            self.composition.strip(),
        ]
        return "\n\n".join(part for part in parts if part)


def _extract_prompt_map(data: dict[str, Any], key: str) -> dict[str, str]:
    section = data.get(key)
    if not isinstance(section, dict) or not section:
        raise ValueError(f"Prompt library must define non-empty '{key}'")

    result: dict[str, str] = {}
    for item_id, value in section.items():
        if isinstance(value, dict):
            prompt = value.get("prompt")
        else:
            prompt = value
        if not isinstance(prompt, str) or not prompt.strip():
            raise ValueError(f"Prompt library '{key}.{item_id}' must define prompt text")
        result[str(item_id)] = prompt
    return result


def load_prompt_library(path: Path) -> PromptLibrary:
    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle)

    if not isinstance(data, dict):
        raise ValueError("Prompt library YAML must contain a mapping")

    base_prompt = data.get("base_prompt")
    if not isinstance(base_prompt, str) or not base_prompt.strip():
        raise ValueError("Prompt library must define base_prompt")

    negative_prompt = data.get("negative_prompt")
    if not isinstance(negative_prompt, str) or not negative_prompt.strip():
        raise ValueError("Prompt library must define negative_prompt")

    composition = data.get("composition", "")
    if not isinstance(composition, str):
        raise ValueError("Prompt library composition must be text")

    return PromptLibrary(
        base_prompt=base_prompt,
        negative_prompt=negative_prompt,
        composition=composition,
        angles=_extract_prompt_map(data, "angles"),
        shots=_extract_prompt_map(data, "shots"),
    )
