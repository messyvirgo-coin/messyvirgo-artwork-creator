from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageFilter

SUPPORTED_INPUT_SUFFIXES = {".jpg", ".jpeg", ".png"}

DEFAULT_SHARPEN_RADIUS = 2.0
DEFAULT_SHARPEN_PERCENT = 130
DEFAULT_SHARPEN_THRESHOLD = 3


@dataclass(frozen=True)
class SharpenSettings:
    radius: float = DEFAULT_SHARPEN_RADIUS
    percent: int = DEFAULT_SHARPEN_PERCENT
    threshold: int = DEFAULT_SHARPEN_THRESHOLD


@dataclass(frozen=True)
class SharpenSummary:
    planned: int
    converted: int
    skipped: int
    failed: int


def sharpen_image(image: Image.Image, settings: SharpenSettings | None = None) -> Image.Image:
    """Apply an unsharp mask to RGB channels, preserving the alpha channel."""
    options = settings or SharpenSettings()
    rgba = image.convert("RGBA")
    rgb = rgba.convert("RGB")
    sharpened_rgb = rgb.filter(
        ImageFilter.UnsharpMask(
            radius=options.radius,
            percent=options.percent,
            threshold=options.threshold,
        )
    )
    return Image.merge("RGBA", (*sharpened_rgb.split(), rgba.getchannel("A")))


def sharpen_file(
    input_path: Path,
    output_path: Path,
    *,
    settings: SharpenSettings | None = None,
) -> None:
    image = Image.open(input_path)
    result = sharpen_image(image, settings=settings)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    result.save(output_path, format="PNG")


def sharpen_images(
    source: Path,
    output_dir: Path,
    *,
    settings: SharpenSettings | None = None,
    overwrite: bool = False,
) -> SharpenSummary:
    inputs = _resolve_inputs(source)
    output_dir.mkdir(parents=True, exist_ok=True)

    converted = 0
    skipped = 0
    failed = 0
    for input_path in inputs:
        output_path = output_dir / f"{input_path.stem}.png"
        if output_path.exists() and not overwrite:
            skipped += 1
            continue
        try:
            sharpen_file(input_path, output_path, settings=settings)
            converted += 1
        except Exception:
            failed += 1
    return SharpenSummary(planned=len(inputs), converted=converted, skipped=skipped, failed=failed)


def _resolve_inputs(source: Path) -> list[Path]:
    if source.is_file():
        if source.suffix.lower() not in SUPPORTED_INPUT_SUFFIXES:
            raise ValueError("Sharpen input must be a JPG, JPEG, or PNG file or directory")
        return [source]
    if source.is_dir():
        return sorted(path for path in source.iterdir() if path.suffix.lower() in SUPPORTED_INPUT_SUFFIXES)
    raise ValueError(f"Sharpen source does not exist: {source}")
