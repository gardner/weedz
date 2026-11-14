"""Uploaded crops keep only their pixels (issue #57): no EXIF, GPS, XMP or comments."""

from io import BytesIO

import pytest
from intake_helpers import jpeg, jpeg_with_gps
from PIL import Image, PngImagePlugin

from weedz.intake.images import ImageRefused, clean_image


def test_exif_gps_xmp_and_comments_are_stripped() -> None:
    original = jpeg_with_gps()
    assert b"SERIAL-123456" in original and b"HomeAddress" in original
    cleaned = clean_image(original, max_pixels=10_000)
    for marker in (b"Exif", b"SERIAL-123456", b"PhoneMaker", b"HomeAddress", b"secret comment"):
        assert marker not in cleaned
    with Image.open(BytesIO(cleaned)) as image:
        assert image.format == "JPEG"
        assert not image.getexif()
        assert not {"exif", "xmp", "icc_profile", "comment"} & image.info.keys()


def test_png_text_chunks_are_dropped_and_the_result_is_jpeg() -> None:
    text = PngImagePlugin.PngInfo()
    text.add_text("Location", "42 Private Road")
    out = BytesIO()
    Image.new("RGBA", (20, 10), (0, 0, 0, 0)).save(out, "PNG", pnginfo=text)
    cleaned = clean_image(out.getvalue(), max_pixels=10_000)
    assert b"Private Road" not in cleaned
    with Image.open(BytesIO(cleaned)) as image:
        assert (image.format, image.size) == ("JPEG", (20, 10))


@pytest.mark.parametrize("fmt", ["PNG", "WEBP"])
def test_transparent_pixels_never_reveal_what_they_hid(fmt: str) -> None:
    """Fully transparent pixels can still hold colour; the stored crop shows white there."""
    out = BytesIO()
    Image.new("RGBA", (16, 16), (255, 0, 0, 0)).save(out, fmt, lossless=True, exact=True)
    with Image.open(BytesIO(clean_image(out.getvalue(), max_pixels=10_000))) as image:
        red, green, blue = image.convert("RGB").getpixel((8, 8))  # type: ignore[misc]
    assert min(red, green, blue) > 240


def test_a_palette_png_with_a_transparent_colour_shows_white_there() -> None:
    out = BytesIO()
    Image.new("P", (16, 16), 0).save(out, "PNG", transparency=0)
    with Image.open(BytesIO(clean_image(out.getvalue(), max_pixels=10_000))) as image:
        assert min(image.convert("RGB").getpixel((8, 8))) > 240  # type: ignore[arg-type]


def test_orientation_is_applied_before_the_metadata_is_dropped() -> None:
    exif = Image.Exif()
    exif[0x0112] = 6  # Orientation: rotate 90 degrees clockwise to display
    cleaned = clean_image(jpeg((60, 20), exif=exif), max_pixels=10_000)
    with Image.open(BytesIO(cleaned)) as image:
        assert image.size == (20, 60)


@pytest.mark.parametrize("fmt", ["GIF", "BMP", "TGA", "PPM"])
def test_only_jpeg_png_and_webp_are_accepted(fmt: str) -> None:
    out = BytesIO()
    Image.new("RGB", (10, 10)).save(out, fmt)
    with pytest.raises(ImageRefused, match="JPEG, PNG or WebP"):
        clean_image(out.getvalue(), max_pixels=10_000)


def test_other_format_parsers_never_see_the_upload(monkeypatch: pytest.MonkeyPatch) -> None:
    """Past Pillow CVEs were in uncommon header parsers such as PSD's."""
    from PIL import PsdImagePlugin

    parsed: list[bool] = []
    monkeypatch.setattr(PsdImagePlugin.PsdImageFile, "_open", lambda _self: parsed.append(True))
    with pytest.raises(ImageRefused):
        clean_image(b"8BPS" + bytes(100), max_pixels=10_000)
    assert parsed == []


def test_a_side_longer_than_jpeg_allows_is_refused() -> None:
    out = BytesIO()
    Image.new("L", (70_000, 1)).save(out, "PNG")
    with pytest.raises(ImageRefused, match="side"):
        clean_image(out.getvalue(), max_pixels=100_000)


def test_too_many_pixels_are_refused_before_decoding() -> None:
    with pytest.raises(ImageRefused, match="pixels"):
        clean_image(jpeg((200, 100)), max_pixels=10_000)


def test_unexpected_pillow_errors_are_refusals_not_crashes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def broken(_image: Image.Image) -> Image.Image:
        raise ValueError("corrupt EXIF IFD")

    monkeypatch.setattr("weedz.intake.images.ImageOps.exif_transpose", broken)
    with pytest.raises(ImageRefused, match="not a readable JPEG, PNG or WebP image"):
        clean_image(jpeg(), max_pixels=10_000)


def test_bytes_that_are_not_an_image_are_refused() -> None:
    with pytest.raises(ImageRefused, match="not a readable JPEG, PNG or WebP image"):
        clean_image(b"\xff\xd8 truncated", max_pixels=10_000)
