from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from PIL import Image

from .sharpen import SharpenSettings, sharpen_image

RemovalMethod = Literal["flood", "rembg"]
DEFAULT_REMBG_MODEL = "isnet-anime"
DEFAULT_WHITE_THRESHOLD = 242
DEFAULT_MAX_NEUTRAL_SPREAD = 18
DEFAULT_FRINGE_ALPHA = 220

SUPPORTED_INPUT_SUFFIXES = {".jpg", ".jpeg", ".png"}
_REMBG_SESSIONS: dict[str, Any] = {}


@dataclass(frozen=True)
class BackgroundRemovalSummary:
    planned: int
    converted: int
    skipped: int
    failed: int


def remove_backgrounds(
    source: Path,
    output_dir: Path,
    *,
    method: RemovalMethod = "rembg",
    model: str = DEFAULT_REMBG_MODEL,
    tolerance: int = 28,
    white_threshold: int = DEFAULT_WHITE_THRESHOLD,
    alpha_matting: bool = False,
    pre_sharpen: bool = True,
    sharpen: SharpenSettings | None = None,
    overwrite: bool = False,
) -> BackgroundRemovalSummary:
    inputs = _resolve_inputs(source)
    output_dir.mkdir(parents=True, exist_ok=True)

    session = _get_rembg_session(model) if method == "rembg" else None

    converted = 0
    skipped = 0
    failed = 0
    for input_path in inputs:
        output_path = output_dir / f"{input_path.stem}.png"
        if output_path.exists() and not overwrite:
            skipped += 1
            continue
        try:
            remove_background(
                input_path,
                output_path,
                method=method,
                model=model,
                tolerance=tolerance,
                white_threshold=white_threshold,
                alpha_matting=alpha_matting,
                pre_sharpen=pre_sharpen,
                sharpen=sharpen,
                session=session,
            )
            converted += 1
        except Exception:
            failed += 1
    return BackgroundRemovalSummary(planned=len(inputs), converted=converted, skipped=skipped, failed=failed)


def remove_background(
    input_path: Path,
    output_path: Path,
    *,
    method: RemovalMethod = "rembg",
    model: str = DEFAULT_REMBG_MODEL,
    tolerance: int = 28,
    white_threshold: int = DEFAULT_WHITE_THRESHOLD,
    alpha_matting: bool = False,
    pre_sharpen: bool = True,
    sharpen: SharpenSettings | None = None,
    session: Any | None = None,
) -> None:
    if method == "rembg":
        _remove_background_rembg(
            input_path,
            output_path,
            model=model,
            session=session,
            white_threshold=white_threshold,
            alpha_matting=alpha_matting,
            pre_sharpen=pre_sharpen,
            sharpen=sharpen,
        )
        return
    _remove_background_flood(
        input_path,
        output_path,
        tolerance=tolerance,
        pre_sharpen=pre_sharpen,
        sharpen=sharpen,
    )


def _remove_background_rembg(
    input_path: Path,
    output_path: Path,
    *,
    model: str,
    session: Any | None,
    white_threshold: int,
    alpha_matting: bool,
    pre_sharpen: bool,
    sharpen: SharpenSettings | None,
) -> None:
    try:
        from rembg import remove as rembg_remove
    except ImportError as exc:
        raise ImportError(
            "AI background removal requires rembg with an ONNX runtime. Install with: "
            'pip install -e ".[rembg]"  (or: pip install "rembg[cpu]")'
        ) from exc

    image = Image.open(input_path).convert("RGBA")
    if pre_sharpen:
        image = sharpen_image(image, settings=sharpen)
    active_session = session if session is not None else _get_rembg_session(model)
    result = rembg_remove(
        image,
        session=active_session,
        alpha_matting=alpha_matting,
        post_process_mask=True,
    )
    if white_threshold > 0:
        _strip_near_white_remnants(result, threshold=white_threshold)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    result.save(output_path, format="PNG")


def _strip_near_white_remnants(
    image: Image.Image,
    *,
    threshold: int = DEFAULT_WHITE_THRESHOLD,
    max_neutral_spread: int = DEFAULT_MAX_NEUTRAL_SPREAD,
    fringe_alpha: int = DEFAULT_FRINGE_ALPHA,
) -> Image.Image:
    """Remove leftover white background trapped inside the mask (hair gaps, between legs)."""
    pixels = image.load()
    width, height = image.size
    for y in range(height):
        for x in range(width):
            red, green, blue, alpha = pixels[x, y]
            if alpha == 0:
                continue
            spread = max(red, green, blue) - min(red, green, blue)
            if red >= threshold and green >= threshold and blue >= threshold and spread <= max_neutral_spread:
                pixels[x, y] = (0, 0, 0, 0)
                continue
            if (
                alpha < fringe_alpha
                and red >= threshold - 12
                and green >= threshold - 12
                and blue >= threshold - 12
                and spread <= max_neutral_spread
            ):
                pixels[x, y] = (0, 0, 0, 0)
    return image


def _get_rembg_session(model: str) -> Any:
    if model not in _REMBG_SESSIONS:
        try:
            from rembg import new_session
        except ImportError as exc:
            raise ImportError(
                "AI background removal requires rembg. Install with: "
                'pip install -e ".[rembg]"  (or: pip install "rembg[cpu]")'
            ) from exc
        _REMBG_SESSIONS[model] = new_session(model)
    return _REMBG_SESSIONS[model]


def _remove_background_flood(
    input_path: Path,
    output_path: Path,
    *,
    tolerance: int,
    pre_sharpen: bool,
    sharpen: SharpenSettings | None,
) -> None:
    image = Image.open(input_path).convert("RGBA")
    if pre_sharpen:
        image = sharpen_image(image, settings=sharpen)
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
            raise ValueError("Background removal input must be a JPG, JPEG, or PNG file or directory")
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
