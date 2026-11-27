"""Count localization error modes against independently labeled instance masks."""

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from weedz.region_evaluation.matching import match_regions

MaskArray = NDArray[np.bool_]


@dataclass(frozen=True)
class MaskErrors:
    matched_truth: tuple[int, ...]
    duplicate_proposals: tuple[int, ...]
    fragmented_truth: tuple[int, ...]
    merged_proposals: tuple[int, ...]


def _areas(truth: MaskArray, proposals: MaskArray) -> tuple[NDArray, NDArray]:
    if truth.ndim != 3 or proposals.ndim != 3 or truth.shape[1:] != proposals.shape[1:]:
        raise ValueError("Ground truth and proposals must use the same source grid")
    if truth.dtype != np.bool_ or proposals.dtype != np.bool_:
        raise ValueError("Masks must contain binary Boolean values")
    if max(len(truth), len(proposals)) > 1000:
        raise ValueError("Mask diagnostics support at most 1000 instances per side")
    truth_area, proposal_area = truth.sum(axis=(1, 2)), proposals.sum(axis=(1, 2))
    if (truth_area == 0).any() or (proposal_area == 0).any():
        raise ValueError("Instance masks must contain foreground pixels")
    return truth_area, proposal_area


def _fragmented(truth: MaskArray, proposals: MaskArray, coverage: NDArray, purity: NDArray) -> bool:
    pieces = (coverage >= 0.10) & (purity >= 0.80)
    if np.count_nonzero(pieces) < 2:
        return False
    union = np.any(proposals[pieces][:, truth], axis=0).mean()
    return bool(union >= 0.50 and union - coverage[pieces].max() >= 0.20 - 1e-12)


def analyze_masks(
    truth: MaskArray, proposals: MaskArray, *, iou_threshold: float = 0.5
) -> MaskErrors:
    """Report one-to-one recovery and localize distinct failure modes.

    Repeats are unmatched proposals with qualifying IoU against a matched
    instance. Fragmentation requires no qualifying individual proposal and
    two or more mostly contained pieces whose union recovers additional area.
    Merges cover at least 20% of each of two or more source instances.
    Unmatched proposals in general cannot be interpreted as false positives.
    """
    truth_area, proposal_area = _areas(truth, proposals)
    intersection = np.empty((len(truth), len(proposals)), dtype=np.int64)
    for i, mask in enumerate(truth):
        intersection[i] = proposals[:, mask].sum(axis=1)
    coverage = intersection / truth_area[:, None]
    purity = intersection / proposal_area[None, :]
    iou = intersection / (truth_area[:, None] + proposal_area[None, :] - intersection)
    matches = match_regions(iou.tolist(), threshold=iou_threshold, proposal_count=len(proposals))
    matched = tuple(row.truth for row in matches.matches)
    duplicates = tuple(
        index
        for index in matches.unmatched_proposals
        if np.any(iou[list(matched), index] >= iou_threshold)
    )
    fragments = tuple(
        i
        for i in matches.missed_truth
        if not np.any(iou[i] >= iou_threshold)
        and _fragmented(truth[i], proposals, coverage[i], purity[i])
    )
    merges = tuple(int(i) for i in np.flatnonzero((coverage >= 0.20).sum(axis=0) >= 2))
    return MaskErrors(matched, duplicates, fragments, merges)
