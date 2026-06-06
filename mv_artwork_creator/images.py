from __future__ import annotations

from io import BytesIO
from pathlib import Path

from PIL import Image

SUPPORTED_REFERENCE_IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}
_SUFFIX_TO_MIME = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
}
_FORMAT_TO_MIME = {
    "JPEG": "image/jpeg",
    "PNG": "image/png",
    "WEBP": "image/webp",
}


def load_image_for_provider(path: Path) -> tuple[bytes, str]:
    if not path.exists():
        raise ValueError(f"Source image does not exist: {path}")
    if not path.is_file():
        raise ValueError(f"Source image is not a file: {path}")

    suffix = path.suffix.lower()
    if suffix not in SUPPORTED_REFERENCE_IMAGE_SUFFIXES:
        supported = ", ".join(sorted(SUPPORTED_REFERENCE_IMAGE_SUFFIXES))
        raise ValueError(f"Source image must be one of: {supported}")

    data = path.read_bytes()
    if not data:
        raise ValueError(f"Source image is empty: {path}")

    mime_type = _detect_mime_type(data, suffix)
    return data, mime_type


def _detect_mime_type(data: bytes, suffix: str) -> str:
    try:
        with Image.open(BytesIO(data)) as image:
            image.verify()
    except Exception as exc:
        raise ValueError("Source image is not a valid PNG, JPEG, or WebP file") from exc

    with Image.open(BytesIO(data)) as image:
        format_name = image.format
        if format_name in _FORMAT_TO_MIME:
            return _FORMAT_TO_MIME[format_name]

    return _SUFFIX_TO_MIME[suffix]
