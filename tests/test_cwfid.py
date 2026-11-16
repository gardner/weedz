"""Functional publisher masks retain uncertainty and overlapping native splits."""

from io import BytesIO

import numpy as np
import pytest
from PIL import Image

from weedz.labelled.cwfid import masks, memberships


def png(array):
    out = BytesIO()
    Image.fromarray(np.asarray(array, dtype=np.uint8)).save(out, format="PNG")
    return out.getvalue()


def test_unassigned_vegetation_is_not_assessed_background():
    classes = png([[[255, 0, 0], [0, 255, 0], [0, 0, 0], [0, 0, 0]]])
    vegetation = png([[0, 0, 0, 255]])
    result = masks(classes, vegetation, (4, 1))
    assert list(result["weed"].get_flattened_data()) == [255, 0, 0, 0]
    assert list(result["crop"].get_flattened_data()) == [0, 255, 0, 0]
    assert list(result["vegetation"].get_flattened_data()) == [255, 255, 255, 0]
    assert list(result["assessed"].get_flattened_data()) == [255, 255, 0, 0]


def test_class_pixels_must_be_vegetation():
    with pytest.raises(ValueError, match="vegetation"):
        masks(png([[[255, 0, 0]]]), png([[255]]), (1, 1))


def test_source_split_overlap_preserved():
    assert memberships(28, {"train": [2, 28], "test": [1, 28]}) == ("train", "test")
    assert memberships(2, {"train": [2, 28], "test": [1, 28]}) == ("train",)
