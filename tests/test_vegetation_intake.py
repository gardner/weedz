import numpy as np
import pytest

from weedz.discovery.vegetation import IntakePhoto, rank_for_review, vegetation_fraction


def test_vegetation_mapping_uses_model_indices_and_excludes_field() -> None:
    labels = np.array([[4, 9, 17, 66], [72, 29, 68, 94]], dtype=np.uint8)
    assert vegetation_fraction(labels) == 5 / 8
    with pytest.raises(ValueError, match="ADE20K label grid"):
        vegetation_fraction(np.array([[150]], dtype=np.int16))


def test_review_ranking_keeps_low_scores_and_breaks_ties_deterministically() -> None:
    rows = [IntakePhoto("z", 0.9), IntakePhoto("low", 0.0), IntakePhoto("a", 0.9)]
    ranked = rank_for_review(rows)
    assert [row.sample_id for row in ranked] == ["a", "z", "low"]
    with pytest.raises(ValueError, match="Duplicate"):
        rank_for_review(rows + [IntakePhoto("a", 0.5)])
    with pytest.raises(ValueError, match="fraction"):
        IntakePhoto("a", float("nan"))
