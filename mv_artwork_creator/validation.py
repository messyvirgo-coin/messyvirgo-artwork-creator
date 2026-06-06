from __future__ import annotations

from pathlib import Path


PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
PNG_COLOR_TYPES_WITH_ALPHA = {4, 6}
PNG_PALETTE_COLOR_TYPE = 3


def validate_png_alpha(path: Path) -> None:
    if path.suffix.lower() != ".png":
        raise ValueError("Source avatar must be a transparent PNG file")
    if not path.exists():
        raise ValueError(f"Source avatar does not exist: {path}")
    if not path.is_file():
        raise ValueError(f"Source avatar is not a file: {path}")

    data = path.read_bytes()
    header = data[:33]

    if len(header) < 33 or not header.startswith(PNG_SIGNATURE):
        raise ValueError("Source avatar must be a transparent PNG file")

    chunk_type = header[12:16]
    if chunk_type != b"IHDR":
        raise ValueError("PNG source is missing the IHDR header")

    color_type = header[25]
    has_alpha_channel = color_type in PNG_COLOR_TYPES_WITH_ALPHA
    has_transparency_chunk = color_type == PNG_PALETTE_COLOR_TYPE and b"tRNS" in data
    if not has_alpha_channel and not has_transparency_chunk:
        raise ValueError("Source PNG must include an alpha channel for transparency")
