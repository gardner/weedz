"""Explicit source-coordinate image profiles; annotation frames are never guessed."""

from dataclasses import dataclass
from io import BytesIO

from PIL import Image

from weedz.labelled.pixels import pixel_sha256

FORMATS = ("lossless-rgb-png", "original-jpeg")


@dataclass(frozen=True)
class PreparedImage:
    encoded: bytes
    pixel_sha256: str
    source_format: str
    source_frames: int
    output_format: str


def prepare_image(raw: bytes, size: tuple[int, int], profile: str) -> PreparedImage:
    if profile not in FORMATS:
        raise ValueError("Unknown external image format profile")
    with Image.open(BytesIO(raw)) as image:
        if image.format not in {"JPEG", "MPO"} or image.getexif().get(274, 1) != 1:
            raise ValueError("Source box frame requires an upright original JPEG")
        if image.size != size or image.width * image.height > 40_000_000:
            raise ValueError("Image dimensions differ from source annotations or exceed budget")
        image.load()
        clean = Image.frombytes("RGB", image.size, image.convert("RGB").tobytes())
        encoded = raw
        output_format = str(image.format)
        if profile == "lossless-rgb-png":
            output = BytesIO()
            clean.save(output, format="PNG")
            encoded = output.getvalue()
            output_format = "PNG"
        if len(encoded) > 160_000_000:
            raise ValueError("External encoded image budget exceeded")
        return PreparedImage(
            encoded,
            pixel_sha256(clean),
            str(image.format),
            getattr(image, "n_frames", 1),
            output_format,
        )
