"""Stored proposal masks retain their pixel identity and original image grid."""

import hashlib

import numpy as np
import pytest
from PIL import Image

from weedz.region_evaluation.proposal_masks import proposal_mask
from weedz.segmentation.regions import region_from_mask


def record() -> dict:
    pixels = np.array([[True, False], [False, True]])
    return region_from_mask(
        Image.new("RGB", (4, 4)), pixels, {}, max_side=64, context_fraction=0
    ).record()


def test_low_resolution_mask_is_aligned_with_nearest_source_pixels() -> None:
    result = proposal_mask(record(), size=(4, 4), kind="sam2")
    assert result.shape == (4, 4)
    assert int(result.sum()) == 8
    assert result[:2, :2].all()
    assert not result[:2, 2:].any()


def test_changed_mask_identity_and_shape_are_refused() -> None:
    for field, value in (("id", "0" * 64), ("mask_size", [3, 3])):
        with pytest.raises(ValueError):
            proposal_mask(record() | {field: value}, size=(4, 4), kind="sam2")


def test_sam3_identity_keeps_prompt_without_treating_it_as_truth() -> None:
    source = record()
    pixels = np.array([[True, False], [False, True]])
    source.update(prompt="plant", id=hashlib.sha256(b"plant\0" + pixels.tobytes()).hexdigest())
    assert int(proposal_mask(source, size=(4, 4), kind="sam3").sum()) == 8
    with pytest.raises(ValueError, match="identity"):
        proposal_mask(source, size=(4, 4), kind="sam2")
