import numpy as np
import pytest

from weedz.classification.plantclef import ranked_species


def test_topk_keeps_alternatives_and_normalizes_against_all_classes():
    rows = ranked_species(np.array([0.0, 0.0, 0.0, 0.0]), ("A", "B", "C", "D"), 2)
    assert [row["taxon"] for row in rows] == ["A", "B"]
    assert [row["score"] for row in rows] == [0.25, 0.25]
    assert {row["score_kind"] for row in rows} == {"closed_set_softmax_uncalibrated"}


@pytest.mark.parametrize("bad", [np.nan, np.inf, -np.inf])
def test_nonfinite_output_is_failure_not_a_species_prediction(bad):
    with pytest.raises(ValueError, match="finite"):
        ranked_species(np.array([0.0, bad]), ("A", "B"), 1)


def test_class_mapping_cannot_silently_truncate_or_duplicate_species():
    with pytest.raises(ValueError, match="mapping"):
        ranked_species(np.array([1.0, 2.0]), ("A",), 1)
    with pytest.raises(ValueError, match="mapping"):
        ranked_species(np.array([1.0, 2.0]), ("A", "A"), 1)
