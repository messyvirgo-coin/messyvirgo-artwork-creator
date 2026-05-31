from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from pathlib import Path

from PIL import Image


SUPPORTED_INPUT_SUFFIXES = {".jpg", ".jpeg"}


@dataclass(frozen=True)
class BackgroundRemovalSummary:
    planned: int
    converted: int
    skipped: int
    failed: int


def remove_backgrounds(source: Path, output_dir: Path, *, tolerance: int = 28, overwrite: bool = False) -> BackgroundRemovalSummary:
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
            remove_background(input_path, output_path, tolerance=tolerance)
            converted += 1
        except Exception:
            failed += 1
    return BackgroundRemovalSummary(planned=len(inputs), converted=converted, skipped=skipped, failed=failed)


def remove_background(input_path: Path, output_path: Path, *, tolerance: int = 28) -> None:
    image = Image.open(input_path).convert("RGBA")
    pixels = image.load()
    width, height = image.size
    background = _average_corner_color(image)
    remove_mask = _edge_connected_background_mask(image, background, tolerance)

    for y in range(height):
        for x in range(width):
            if remove_mask[y][x]:
                r, g, b, _a = pixels[x, y]
                pixels[x, y] = (r, g, b, 0)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(output_path, format="PNG")


def _resolve_inputs(source: Path) -> list[Path]:
    if source.is_file():
        if source.suffix.lower() not in SUPPORTED_INPUT_SUFFIXES:
            raise ValueError("Background removal input must be a JPG/JPEG file or directory")
        return [source]
    if source.is_dir():
        return sorted(path for path in source.iterdir() if path.suffix.lower() in SUPPORTED_INPUT_SUFFIXES)
    raise ValueError(f"Background removal source does not exist: {source}")


def _average_corner_color(image: Image.Image) -> tuple[int, int, int]:
    width, height = image.size
    samples = [
        image.getpixel((0, 0))[:3],
        image.getpixel((width - 1, 0))[:3],
        image.getpixel((0, height - 1))[:3],
        image.getpixel((width - 1, height - 1))[:3],
    ]
    return tuple(round(sum(sample[channel] for sample in samples) / len(samples)) for channel in range(3))


def _edge_connected_background_mask(
    image: Image.Image,
    background: tuple[int, int, int],
    tolerance: int,
) -> list[list[bool]]:
    width, height = image.size
    visited = [[False for _x in range(width)] for _y in range(height)]
    remove_mask = [[False for _x in range(width)] for _y in range(height)]
    queue: deque[tuple[int, int]] = deque()

    for x in range(width):
        queue.append((x, 0))
        queue.append((x, height - 1))
    for y in range(height):
        queue.append((0, y))
        queue.append((width - 1, y))

    while queue:
        x, y = queue.popleft()
        if x < 0 or x >= width or y < 0 or y >= height or visited[y][x]:
            continue
        visited[y][x] = True
        if not _is_background_pixel(image.getpixel((x, y))[:3], background, tolerance):
            continue
        remove_mask[y][x] = True
        queue.extend(((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)))

    return remove_mask


def _is_background_pixel(color: tuple[int, int, int], background: tuple[int, int, int], tolerance: int) -> bool:
    distance = sum((color[index] - background[index]) ** 2 for index in range(3)) ** 0.5
    return distance <= tolerance
