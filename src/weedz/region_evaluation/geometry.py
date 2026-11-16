"""Overlap primitives in upright, exclusive-edge source-image coordinates."""

import math
from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

type Box = tuple[float, float, float, float]


def _area(box: Box) -> float:
    if not all(math.isfinite(value) for value in box):
        raise ValueError("A box must have finite coordinates")
    left, top, right, bottom = box
    if left < 0 or top < 0 or right <= left or bottom <= top:
        raise ValueError("A box must have positive area and nonnegative coordinates")
    area = (right - left) * (bottom - top)
    if not math.isfinite(area):
        raise ValueError("A box area must be finite")
    return area


def box_iou(truth: Box, prediction: Box) -> float:
    """No inclusive-pixel +1 correction; touching edges have zero intersection."""
    truth_area, predicted_area = _area(truth), _area(prediction)
    width = max(0.0, min(truth[2], prediction[2]) - max(truth[0], prediction[0]))
    height = max(0.0, min(truth[3], prediction[3]) - max(truth[1], prediction[1]))
    intersection = width * height
    return intersection / (truth_area + predicted_area - intersection)


@dataclass(frozen=True)
class MaskOverlap:
    truth_pixels: int
    predicted_pixels: int
    intersection_pixels: int
    iou: float | None
    dice: float | None


def mask_overlap(truth: NDArray[np.generic], prediction: NDArray[np.generic]) -> MaskOverlap:
    """Empty/empty overlap is undefined, never evidence of a correct negative."""
    if truth.dtype != np.bool_ or prediction.dtype != np.bool_:
        raise ValueError("Masks must contain boolean pixels")
    if truth.ndim != 2 or truth.shape != prediction.shape or not truth.size:
        raise ValueError("Masks must share a nonempty two-dimensional pixel grid")
    true_count = int(np.count_nonzero(truth))
    predicted_count = int(np.count_nonzero(prediction))
    intersection = int(np.count_nonzero(np.logical_and(truth, prediction)))
    union = true_count + predicted_count - intersection
    total = true_count + predicted_count
    return MaskOverlap(
        true_count,
        predicted_count,
        intersection,
        intersection / union if union else None,
        2 * intersection / total if total else None,
    )
