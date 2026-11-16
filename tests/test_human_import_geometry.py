"""Strict offline human geometry: no model-to-truth or implicit mask-to-box conversion."""

import numpy as np
import pytest
from label_studio_sdk.converter.brush import mask2rle

from weedz.annotation.import_geometry import decode_region


def rectangle():
    return {
        "id": "r1",
        "from_name": "review_boxes",
        "to_name": "image",
        "type": "rectanglelabels",
        "original_width": 200,
        "original_height": 100,
        "image_rotation": 0,
        "value": {
            "x": 10,
            "y": 20,
            "width": 50,
            "height": 30,
            "rotation": 0,
            "rectanglelabels": ["Ulex europaeus"],
        },
    }


def test_rectangle_percentages_retain_original_pixel_coordinates():
    result = decode_region(rectangle(), (200, 100), {"Ulex europaeus"})
    assert result.box == (20, 20, 120, 50)
    assert result.mask is None
    assert result.taxon == "Ulex europaeus"


@pytest.mark.parametrize("change", ["rotation", "extent", "geometry", "unknown", "nan"])
def test_invalid_geometry_is_refused(change):
    row = rectangle()
    if change == "rotation":
        row["value"]["rotation"] = 90
    elif change == "extent":
        row["value"]["width"] = 99
    elif change == "geometry":
        row["original_width"] = 201
    elif change == "unknown":
        row["value"]["rectanglelabels"] = ["model guess"]
    else:
        row["value"]["x"] = float("nan")
    with pytest.raises(ValueError):
        decode_region(row, (200, 100), {"Ulex europaeus"})


def test_brush_roundtrip_stays_a_mask():
    mask = np.zeros((3, 4), dtype=np.uint8)
    mask[1, 1:3] = 255
    row = {
        "id": "b",
        "from_name": "regions",
        "to_name": "image",
        "type": "brushlabels",
        "original_width": 4,
        "original_height": 3,
        "image_rotation": 0,
        "value": {"format": "rle", "rle": mask2rle(mask), "brushlabels": ["Ulex europaeus"]},
    }
    decoded = decode_region(row, (4, 3), {"Ulex europaeus"})
    assert decoded.box is None
    assert decoded.mask is not None
    import io

    from PIL import Image

    assert np.array_equal(np.asarray(Image.open(io.BytesIO(decoded.mask))), mask)
