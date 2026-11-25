"""Region diagnostics distinguish a fragmented plant from repeat proposals."""

import numpy as np
import pytest

from weedz.region_evaluation.mask_errors import analyze_masks


def test_repeated_mask_is_a_duplicate_and_cannot_add_recall() -> None:
    plant = np.ones((2, 10), dtype=bool)
    result = analyze_masks(np.stack([plant]), np.stack([plant, plant]))
    assert result.matched_truth == (0,)
    assert result.duplicate_proposals == (1,)
    assert result.fragmented_truth == ()


def test_fragments_require_distinct_useful_coverage() -> None:
    plant = np.ones((2, 10), dtype=bool)
    left = np.zeros_like(plant)
    right = np.zeros_like(plant)
    left[:, :4] = True
    right[:, 6:] = True
    result = analyze_masks(np.stack([plant]), np.stack([left, right]))
    assert result.matched_truth == ()
    assert result.duplicate_proposals == ()
    assert result.fragmented_truth == (0,)
    repeated = analyze_masks(np.stack([plant]), np.stack([left, left]))
    assert repeated.fragmented_truth == ()


def test_one_proposal_covering_two_plants_is_flagged() -> None:
    left = np.array([[True, True, False, False]])
    right = ~left
    result = analyze_masks(np.stack([left, right]), np.stack([left | right]))
    assert len(result.matched_truth) == 1
    assert result.merged_proposals == (0,)


def test_no_proposal_is_a_miss_and_shape_mismatch_is_rejected() -> None:
    truth = np.ones((1, 2, 3), dtype=bool)
    result = analyze_masks(truth, np.empty((0, 2, 3), dtype=bool))
    assert result.matched_truth == result.fragmented_truth == result.merged_proposals == ()
    with pytest.raises(ValueError, match="same source grid"):
        analyze_masks(truth, np.ones((1, 3, 2), dtype=bool))
