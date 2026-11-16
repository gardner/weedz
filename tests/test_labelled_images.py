"""High-resolution PNG preparation preserves the publisher's pixel coordinate frame."""

from io import BytesIO

import pytest
from PIL import Image

from weedz.labelled.images import prepare_image


def source(orientation=1):
    image = Image.new("RGB", (7, 5), (20, 70, 110))
    exif = Image.Exif()
    exif[274] = orientation
    out = BytesIO()
    image.save(out, format="JPEG", exif=exif)
    return out.getvalue()


def test_lossless_profile_preserves_decoded_source_pixels_and_removes_metadata():
    raw = source()
    prepared = prepare_image(raw, (7, 5), "lossless-rgb-png")
    with Image.open(BytesIO(raw)) as original, Image.open(BytesIO(prepared.encoded)) as clean:
        assert clean.size == original.size and clean.tobytes() == original.convert("RGB").tobytes()
        assert clean.format == "PNG" and not clean.getexif()
    assert prepare_image(raw, (7, 5), "original-jpeg").encoded == raw


def test_ambiguous_orientation_and_geometry_refused():
    with pytest.raises(ValueError, match="upright"):
        prepare_image(source(6), (7, 5), "lossless-rgb-png")
    with pytest.raises(ValueError, match="dimensions"):
        prepare_image(source(), (5, 7), "lossless-rgb-png")


def test_verified_prepared_png_can_be_reused_without_accepting_different_pixels():
    raw = source()
    prepared = prepare_image(raw, (7, 5), "lossless-rgb-png")
    reused = prepare_image(raw, (7, 5), "lossless-rgb-png", prepared_png=prepared.encoded)
    assert reused.encoded == prepared.encoded and reused.pixel_sha256 == prepared.pixel_sha256
    wrong = BytesIO()
    Image.new("RGB", (7, 5), "red").save(wrong, format="PNG")
    with pytest.raises(ValueError, match="pixels"):
        prepare_image(raw, (7, 5), "lossless-rgb-png", prepared_png=wrong.getvalue())
