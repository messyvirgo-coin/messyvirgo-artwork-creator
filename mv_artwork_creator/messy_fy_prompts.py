from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True)
class MessyFyPromptLibrary:
    system_prompt: str
    negative_prompt: str

    def compose_prompt(self, *, hint: str | None = None) -> str:
        hint = (hint or "").strip()
        hint_section = ""
        if hint:
            hint_section = f"Additional guidance: {hint}"

        try:
            return self.system_prompt.format(hint_section=hint_section).strip()
        except KeyError as exc:
            raise ValueError(f"Messy-fy prompt references unknown placeholder: {exc}") from exc


def load_messy_fy_prompt_library(path: Path) -> MessyFyPromptLibrary:
    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle)

    if not isinstance(data, dict):
        raise ValueError("Messy-fy prompt YAML must contain a mapping")

    system_prompt = _required_text(data, "system_prompt")
    negative_prompt = _required_text(data, "negative_prompt")
    return MessyFyPromptLibrary(system_prompt=system_prompt, negative_prompt=negative_prompt)


def _required_text(data: dict[str, Any], key: str) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Messy-fy prompt library must define {key}")
    return value
