"""Keep only an uploaded crop's pixels (issue #57).

Metadata hides in many places (EXIF with GPS and camera serials, XMP, IPTC, maker notes,
ICC profiles, PNG text chunks, comments), so nothing is stripped in place. The image is
decoded, its orientation applied, and the bare pixels are copied into a new image that
is saved as a fresh JPEG with no metadata at all.
"""

from io import BytesIO

from PIL import Image, ImageOps

ACCEPTED = {"JPEG", "PNG", "WEBP"}


class ImageRefused(ValueError):
    """An upload that is not a small JPEG, PNG or WebP image."""


def clean_image(data: bytes, max_pixels: int) -> bytes:
    """The image's pixels as a metadata-free JPEG; ImageRefused for anything else."""
    try:
        with Image.open(BytesIO(data)) as image:
            # Opening reads only the header, so these checks come before any decoding.
            if image.format not in ACCEPTED:
                raise ImageRefused("Send the crop as JPEG, PNG or WebP")
            if image.width * image.height > max_pixels:
                raise ImageRefused(f"The crop has more than {max_pixels} pixels")
            upright = ImageOps.exif_transpose(image).convert("RGB")
    except ImageRefused:
        raise
    except Exception as error:  # malformed files fail in many ways inside Pillow
        raise ImageRefused("The crop is not a readable image") from error
    bare = Image.frombytes("RGB", upright.size, upright.tobytes())
    out = BytesIO()
    bare.save(out, "JPEG", quality=85)
    return out.getvalue()
