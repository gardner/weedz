"""Decoded identity includes colour mode and geometry, independently of file metadata."""

from PIL import Image

from weedz.labelled.publication import digest


def pixel_sha256(image: Image.Image) -> str:
    rgb = image.convert("RGB")
    header = f"RGB:{rgb.width}x{rgb.height}\0".encode()
    return digest(header + rgb.tobytes())
