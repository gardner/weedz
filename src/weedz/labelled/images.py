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


def prepare_image(
    raw: bytes, size: tuple[int, int], profile: str, *, prepared_png: bytes | None = None
) -> PreparedImage:
    if profile not in FORMATS:
        raise ValueError("Unknown external image format profile")
    with Image.open(BytesIO(raw)) as image:
        if image.format not in {"JPEG", "MPO"} or image.getexif().get(274, 1) != 1:
            raise ValueError("Source box frame requires an upright original JPEG")
        if image.size != size or image.width * image.height > 40_000_000:
            raise ValueError("Image dimensions differ from source annotations or exceed budget")
        image.load()
        clean = Image.frombytes("RGB", image.size, image.convert("RGB").tobytes())
        source_pixel_sha = pixel_sha256(clean)
        encoded = raw
        output_format = str(image.format)
        if profile == "lossless-rgb-png":
            encoded = _png(clean, prepared_png, source_pixel_sha)
            output_format = "PNG"
        elif prepared_png is not None:
            raise ValueError("Prepared PNG cache requires the lossless PNG profile")
        if len(encoded) > 160_000_000:
            raise ValueError("External encoded image budget exceeded")
        return PreparedImage(
            encoded,
            source_pixel_sha,
            str(image.format),
            getattr(image, "n_frames", 1),
            output_format,
        )


def _png(clean: Image.Image, cached: bytes | None, expected_pixels: str) -> bytes:
    if cached is None:
        output = BytesIO()
        clean.save(output, format="PNG")
        return output.getvalue()
    _minimal_png(cached)
    with Image.open(BytesIO(cached)) as image:
        if image.mode != "RGB" or image.size != clean.size or image.info:
            raise ValueError("Prepared PNG geometry, mode or metadata differs from profile")
        if pixel_sha256(image) != expected_pixels:
            raise ValueError("Prepared PNG pixels differ from verified source")
    return cached


def _minimal_png(raw: bytes) -> None:
    header = b"\x89PNG\r\n\x1a\n\x00\x00\x00\x0dIHDR"
    if len(raw) > 160_000_000 or (raw[:16], raw[24:29]) != (header, b"\x08\x02\x00\x00\x00"):
        raise ValueError("Prepared PNG byte budget, header or RGB layout mismatch")
    offset = 33
    has_data = False
    while offset < len(raw):
        length = int.from_bytes(raw[offset : offset + 4], "big")
        kind = raw[offset + 4 : offset + 8]
        end = offset + length + 12
        if end > len(raw):
            raise ValueError("Prepared PNG contains incomplete chunks")
        if kind == b"IEND":
            if (length, end, has_data) != (0, len(raw), True):
                raise ValueError("Prepared PNG requires a complete final image trailer")
            return
        if kind != b"IDAT":
            raise ValueError("Prepared PNG contains metadata or invalid chunk order")
        has_data = True
        offset = end
    raise ValueError("Prepared PNG is not a complete metadata-free image")
