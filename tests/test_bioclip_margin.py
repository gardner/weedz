"""Canonical BioCLIP records keep native margins, never probability-shaped scores."""

import pytest

from weedz.classification.bioclip import candidate, validate_summary
from weedz.discovery.records import SPECIES


def summary(margin=-0.2):
    return {
        "best_species": list(SPECIES)[0],
        "similarity": 0.3,
        "margin": margin,
        "species": [
            {"name": name, "similarity": 0.3, "margin": margin - i * 0.1}
            for i, name in enumerate(SPECIES)
        ],
    }


def test_negative_margins_remain_negative_and_propose_unknown():
    value = summary()
    validate_summary(value)
    assert candidate(value) == "Unknown"
    assert value["margin"] == -0.2
    assert "score" not in value
    assert candidate(summary(0.01)) == list(SPECIES)[0]


@pytest.mark.parametrize("value", [float("nan"), float("inf"), -float("inf")])
def test_nonfinite_never_becomes_a_candidate(value):
    assert candidate(summary(value)) == "Unknown"
    with pytest.raises(ValueError):
        validate_summary(summary(value))


def test_summary_must_preserve_full_watchlist_and_actual_best():
    value = summary()
    value["species"].pop()
    with pytest.raises(ValueError):
        validate_summary(value)
    value = summary()
    value["best_species"] = list(SPECIES)[1]
    with pytest.raises(ValueError):
        validate_summary(value)


def test_margin_not_probability_range():
    value = summary(-1.2)
    validate_summary(value)
    value["species"][0]["similarity"] = 1.1
    with pytest.raises(ValueError):
        validate_summary(value)


def test_frame_screens_only_private_verified_snapshot_and_never_source_taxonomy(monkeypatch):
    import io

    from PIL import Image
    from test_bioclip_batches import score

    from weedz.classification.bioclip import BioClipClassifier

    observed = []

    class Screener:
        metadata = {}

        def screen(self, path, subject=None):
            observed.append((path, path.read_bytes(), subject))
            return score()

    raw = io.BytesIO()
    Image.new("RGB", (1, 1), "green").save(raw, format="PNG")
    model = BioClipClassifier(Screener())
    model.frame(raw.getvalue())
    assert observed[0][1] == raw.getvalue() and observed[0][2] is None
    assert not observed[0][0].exists()


def test_reaggregation_preserves_float32_winning_window_ties():
    import numpy as np

    from weedz.classification.bioclip import validate_scores
    from weedz.discovery.inference import COMPARISONS, summarize_scores

    raw = np.zeros((2, len(SPECIES) + len(COMPARISONS)), dtype=np.float32)
    raw[:, 0] = [0.9, 0.7]
    raw[:, len(SPECIES) :] = np.array([[0.3], [0.1]], dtype=np.float32)
    boxes = [(0, 0, 100, 100), (0, 0, 60, 60)]
    result = summarize_scores(raw, boxes, list(SPECIES) + COMPARISONS, len(SPECIES))
    result.update(window_similarities=raw.tolist(), window_boxes=boxes)
    validate_scores(result, frame=True)
