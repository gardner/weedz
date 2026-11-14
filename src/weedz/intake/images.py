"""Keep only an uploaded crop's pixels (issue #57).

Metadata hides in many places (EXIF with GPS and camera serials, XMP, IPTC, maker notes,
ICC profiles, PNG text chunks, comments), so nothing is stripped in place. The image is
decoded, its orientation applied, and the bare pixels are copied into a new image that
is saved as a fresh JPEG with no metadata at all.
"""

from io import BytesIO

from PIL import Image, ImageOps

ACCEPTED = ("JPEG", "PNG", "WEBP")
UNREADABLE = "The crop is not a readable JPEG, PNG or WebP image"
# The longest side a JPEG can hold.
JPEG_MAX_SIDE = 65_500


class ImageRefused(ValueError):
    """An upload that is not a small JPEG, PNG or WebP image."""


def clean_image(data: bytes, max_pixels: int) -> bytes:
    """The image's pixels as a metadata-free JPEG; ImageRefused for anything else."""
    try:
        # Only these formats' parsers ever see the upload, not every plugin Pillow has.
        with Image.open(BytesIO(data), formats=ACCEPTED) as image:
            # Opening reads only the header, so these checks come before any decoding.
            if image.format not in ACCEPTED:
                raise ImageRefused(UNREADABLE)
            if image.width * image.height > max_pixels:
                raise ImageRefused(f"The crop has more than {max_pixels} pixels")
            if max(image.size) > JPEG_MAX_SIDE:
                raise ImageRefused(f"A crop's side is at most {JPEG_MAX_SIDE} pixels")
            upright = ImageOps.exif_transpose(image).convert("RGB")
    except ImageRefused:
        raise
    except Exception as error:  # malformed files fail in many ways inside Pillow
        raise ImageRefused(UNREADABLE) from error
    bare = Image.frombytes("RGB", upright.size, upright.tobytes())
    out = BytesIO()
    bare.save(out, "JPEG", quality=85)
    return out.getvalue()
