"""One-to-one proposal matching mechanics, without species-dependent assignment."""

import pytest

from weedz.region_evaluation.matching import match_regions


def test_augmenting_assignment_recovers_both_labelled_regions() -> None:
    # Greedy best overlap for proposal 0 would strand proposal 1.
    result = match_regions([[0.9, 0.8], [0.7, 0.0]], threshold=0.5)
    assert {(pair.truth, pair.proposal) for pair in result.matches} == {(1, 0), (0, 1)}
    assert result.missed_truth == ()
    assert result.unmatched_proposals == ()


def test_duplicate_proposals_do_not_inflate_recall() -> None:
    result = match_regions([[0.7, 0.7, 0.1]], threshold=0.5)
    assert len(result.matches) == 1
    assert len(result.unmatched_proposals) == 2


def test_empty_proposals_are_misses_not_true_negatives() -> None:
    result = match_regions([[], []], threshold=0.5)
    assert result.missed_truth == (0, 1)
    assert result.matches == ()


@pytest.mark.parametrize("matrix", [[[float("nan")]], [[1.1]], [[0.3], []]])
def test_invalid_overlap_matrix_refused(matrix: list[list[float]]) -> None:
    with pytest.raises(ValueError):
        match_regions(matrix, threshold=0.5)


def test_threshold_is_inclusive_but_zero_overlap_cannot_match() -> None:
    assert len(match_regions([[0.5]], threshold=0.5).matches) == 1
    with pytest.raises(ValueError):
        match_regions([[0.0]], threshold=0.0)
