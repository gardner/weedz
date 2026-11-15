"""Identify supported encoded images without trusting a cache filename suffix."""

from pathlib import Path

from PIL import Image

MIME_TYPES = {"JPEG": "image/jpeg", "PNG": "image/png", "WEBP": "image/webp"}


def image_media_type(path: Path) -> str:
    try:
        with Image.open(path) as image:
            mime = MIME_TYPES.get(image.format or "")
    except (OSError, Image.DecompressionBombError) as error:
        raise ValueError("Image is not available") from error
    if mime is None:
        raise ValueError("Unsupported encoded image")
    return mime
