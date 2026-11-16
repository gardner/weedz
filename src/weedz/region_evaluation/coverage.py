"""Coverage of supplied positive pixels without inventing unlabelled negatives."""

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from weedz.region_evaluation.geometry import mask_overlap


@dataclass(frozen=True)
class PixelCoverage:
    labelled_pixels: int
    assessed_labelled_pixels: int
    excluded_labelled_pixels: int
    covered_labelled_pixels: int
    coverage: float | None


def sparse_coverage(
    truth: NDArray[np.generic],
    prediction: NDArray[np.generic],
    *,
    assessed: NDArray[np.generic] | None = None,
) -> PixelCoverage:
    """Measure only supplied positive support, never precision, Dice or full-scene recall."""
    overlap = mask_overlap(truth, prediction, assessed=assessed)
    labelled = int(np.count_nonzero(truth))
    selected = overlap.truth_pixels
    return PixelCoverage(
        labelled,
        selected,
        labelled - selected,
        overlap.intersection_pixels,
        overlap.intersection_pixels / selected if selected else None,
    )
