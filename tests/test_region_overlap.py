"""Mechanical overlap tests are not benchmark observations."""

import numpy as np
import pytest

from weedz.region_evaluation.geometry import box_iou, mask_overlap


def test_exclusive_pixel_boxes_and_disjoint_edges() -> None:
    assert box_iou((0, 0, 2, 2), (1, 0, 3, 2)) == pytest.approx(1 / 3)
    assert box_iou((0, 0, 2, 2), (2, 0, 4, 2)) == 0


@pytest.mark.parametrize("box", [(0, 0, 0, 2), (2, 0, 1, 2), (0, 0, float("nan"), 2)])
def test_invalid_boxes_refused(box: tuple[float, float, float, float]) -> None:
    with pytest.raises(ValueError, match="box"):
        box_iou(box, (0, 0, 2, 2))


def test_mask_metrics_use_actual_pixels_not_bounding_rectangles() -> None:
    truth = np.array([[True, False], [False, True]])
    prediction = np.array([[True, True], [False, False]])
    result = mask_overlap(truth, prediction)
    assert result.iou == pytest.approx(1 / 3)
    assert result.dice == 0.5
    assert result.truth_pixels == result.predicted_pixels == 2


def test_empty_masks_do_not_invent_perfect_localisation() -> None:
    result = mask_overlap(np.zeros((2, 2), dtype=bool), np.zeros((2, 2), dtype=bool))
    assert result.iou is None
    assert result.dice is None


def test_different_mask_grids_and_nonbinary_inputs_refused() -> None:
    with pytest.raises(ValueError, match="grid"):
        mask_overlap(np.zeros((2, 2), dtype=bool), np.zeros((3, 2), dtype=bool))
    with pytest.raises(ValueError, match="boolean"):
        mask_overlap(np.zeros((2, 2), dtype=np.uint8), np.zeros((2, 2), dtype=bool))


def test_explicit_void_pixels_are_excluded_from_both_sides() -> None:
    truth = np.array([[True, False], [False, False]])
    prediction = np.ones((2, 2), dtype=bool)
    assessed = np.array([[True, True], [False, False]])
    result = mask_overlap(truth, prediction, assessed=assessed)
    assert result.truth_pixels == 1
    assert result.predicted_pixels == 2
    assert result.iou == 0.5


def test_empty_assessment_does_not_become_a_negative_observation() -> None:
    result = mask_overlap(
        np.ones((2, 2), dtype=bool),
        np.ones((2, 2), dtype=bool),
        assessed=np.zeros((2, 2), dtype=bool),
    )
    assert result.iou is result.dice is None
