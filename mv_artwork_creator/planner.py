from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .config import GenerationConfig
from .presets import resolve_matrix
from .prompts import PromptLibrary
from .validation import validate_png_alpha


@dataclass(frozen=True)
class PlannedImage:
    angle_id: str
    shot_id: str
    prompt: str
    negative_prompt: str
    output_path: Path
    metadata_path: Path


@dataclass(frozen=True)
class GenerationPlan:
    source_image: Path
    output_dir: Path
    model: str
    provider: str
    items: list[PlannedImage]


def create_generation_plan(config: GenerationConfig, prompt_library: PromptLibrary) -> GenerationPlan:
    validate_png_alpha(config.source_image)
    matrix = resolve_matrix(config.presets, config.test_mode, config.test_preset)

    items: list[PlannedImage] = []
    for angle_id, shot_id in matrix:
        filename_stem = f"{angle_id}__{shot_id}"
        items.append(
            PlannedImage(
                angle_id=angle_id,
                shot_id=shot_id,
                prompt=prompt_library.compose_prompt(angle_id, shot_id),
                negative_prompt=prompt_library.negative_prompt,
                output_path=config.output_dir / f"{filename_stem}.png",
                metadata_path=config.output_dir / f"{filename_stem}.json",
            )
        )

    return GenerationPlan(
        source_image=config.source_image,
        output_dir=config.output_dir,
        model=config.model,
        provider="openrouter",
        items=items,
    )
