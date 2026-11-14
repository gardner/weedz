"""The whole-frame versus tiles benchmark file is reproducible and states its limits."""

import importlib.util
from pathlib import Path
from typing import Any

spec = importlib.util.spec_from_file_location(
    "compare_framing", Path(__file__).parents[1] / "scripts" / "compare_framing.py"
)
assert spec and spec.loader
script = importlib.util.module_from_spec(spec)
spec.loader.exec_module(script)


def comparison() -> dict[str, Any]:
    return {
        "labels": {"independent": 0, "source_subject": 1, "lookalike_photos": 0},
        "arms": {},
        "photos": {
            "p": {
                "whole_frame": {"species": "Ulex europaeus", "margin": 0.0123456789, "box": [0]},
                "tiles": None,
            }
        },
    }


def test_document_keeps_provenance_and_rounds_per_photo_margins() -> None:
    metadata = {"model": "m", "model_key": "k", "revision": "r", "weights_sha256": "w", "x": 1}
    found = script.document(comparison(), metadata, {"run": "nelson"}, "2026-11-14")
    assert found["issue"] == "https://github.com/gardner/weedz/issues/12"
    assert found["assessed"] == "2026-11-14"
    assert found["model"] == {key: metadata[key] for key in script.PROVENANCE}
    assert "x" not in found["model"]
    assert found["inputs"] == {"run": "nelson"}
    assert found["photos"]["p"]["whole_frame"] == {"species": "Ulex europaeus", "margin": 0.012346}
    assert found["photos"]["p"]["tiles"] is None
    assert "not measurable" in found["conclusion"]


def test_conclusion_never_claims_a_winner_without_independent_labels() -> None:
    assert "cannot say" in script.conclusion({"independent": 0})
    assert "cannot say" not in script.conclusion({"independent": 3})


def test_lookalike_photos_carry_their_cohort_and_resemblance() -> None:
    items = [
        {"id": "inat-1-2", "lookalike_taxon": "Austroderia", "lookalike_of": "Cortaderia selloana"}
    ]
    photos = script.lookalike_photos(items)
    assert photos == [
        {
            "id": "inat-1-2",
            "cohort": "lookalike",
            "lookalike_taxon": "Austroderia",
            "lookalike_of": "Cortaderia selloana",
            "image": "images/2.jpg",
        }
    ]
