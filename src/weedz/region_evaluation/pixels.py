"""Decoded source identity, independent of lossless PNG compression choices."""

import hashlib
import io

from PIL import Image


def pixel_sha256(encoded: bytes) -> str:
    """Input has already passed the canonical RGB/geometry/checksum ingress."""
    with Image.open(io.BytesIO(encoded)) as image:
        digest = hashlib.sha256(f"RGB:{image.width}:{image.height}:".encode())
        digest.update(image.tobytes())
    return digest.hexdigest()
