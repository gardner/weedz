"""Sparse source positives support coverage, not background correctness."""

import numpy as np

from weedz.region_evaluation.coverage import sparse_coverage


def test_background_predictions_do_not_create_sparse_truth_negatives() -> None:
    truth = np.array([[True, True], [False, False]])
    prediction = np.array([[True, False], [True, True]])
    result = sparse_coverage(truth, prediction, assessed=truth)
    assert result.labelled_pixels == result.assessed_labelled_pixels == 2
    assert result.covered_labelled_pixels == 1
    assert result.coverage == 0.5


def test_unassessed_labelled_pixels_are_reported_not_silently_counted() -> None:
    truth = np.ones((2, 2), dtype=bool)
    assessed = np.array([[True, False], [False, False]])
    result = sparse_coverage(truth, truth, assessed=assessed)
    assert result.labelled_pixels == 4
    assert result.assessed_labelled_pixels == 1
    assert result.excluded_labelled_pixels == 3
    assert result.coverage == 1


def test_no_assessed_positives_has_no_coverage_denominator() -> None:
    result = sparse_coverage(np.zeros((2, 2), dtype=bool), np.ones((2, 2), dtype=bool))
    assert result.coverage is None
