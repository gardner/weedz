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


def test_rle_declared_allocation_is_checked_before_sdk_decode(monkeypatch):
    import label_studio_sdk.converter.brush as brush

    monkeypatch.setattr(brush, "decode_rle", lambda *_: pytest.fail("unsafe allocation"))
    row = {
        "id": "b",
        "from_name": "regions",
        "to_name": "image",
        "type": "brushlabels",
        "original_width": 4,
        "original_height": 3,
        "image_rotation": 0,
        "value": {"format": "rle", "rle": [255, 255, 255, 255], "brushlabels": ["Ulex"]},
    }
    with pytest.raises(ValueError, match="size"):
        decode_region(row, (4, 3), {"Ulex"})


@pytest.mark.parametrize("edge", ["right", "bottom", "both"])
def test_edge_clamped_percentages_allow_only_float_roundoff(edge):
    import copy

    row = rectangle()
    row.update(original_width=1536, original_height=1536)
    start, extent = 7 / 1536 * 100, (1536 - 7) / 1536 * 100
    assert start + extent > 100  # Actual separately computed Label Studio percentages.
    if edge in {"right", "both"}:
        row["value"].update(x=start, width=extent)
    if edge in {"bottom", "both"}:
        row["value"].update(y=start, height=extent)
    original = copy.deepcopy(row)
    region = decode_region(row, (1536, 1536), {"Ulex europaeus"})
    assert region.box is not None
    if edge in {"right", "both"}:
        assert region.box[0] == pytest.approx(7)
        assert region.box[2] == 1536
    if edge in {"bottom", "both"}:
        assert region.box[1] == pytest.approx(7)
        assert region.box[3] == 1536
    assert row == original  # Revision identity still binds the original export values.


@pytest.mark.parametrize("x,width", [(0.4557291666666667, 99.544272), (100, 1e-12)])
def test_edge_tolerance_does_not_admit_outside_or_empty_boxes(x, width):
    row = rectangle()
    row["value"].update(x=x, width=width)
    with pytest.raises(ValueError, match="inside original image"):
        decode_region(row, (200, 100), {"Ulex europaeus"})
