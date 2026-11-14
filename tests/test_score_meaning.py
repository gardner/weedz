"""Screening scores carry a declared meaning, versioned with the model and ranking (#16)."""

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from test_outcomes_surface import pilot

from weedz.discovery.activities import export
from weedz.discovery.api import create_app
from weedz.discovery.inference import MODELS
from weedz.discovery.score_meaning import DECLARED, score_meaning
from weedz.discovery.store import Store

BENCHMARKS = Path(__file__).parents[1] / "benchmarks"


def model(key: str | None = "bioclip-2", ranking: int = 4, **extra: object) -> dict:
    """Run model metadata as the screener records it."""
    metadata: dict = {"ranking_revision": ranking, "calibrated": False, **extra}
    if key is not None:
        metadata |= {"model_key": key, "revision": MODELS[key]["revision"]}
    return metadata


def test_bioclip_2_ranking_4_has_a_declared_meaning() -> None:
    meaning = score_meaning(model())
    assert meaning["declared"] is True
    assert meaning["id"] == "bioclip-2/ranking-4/meaning-1"
    assert meaning["model_key"] == "bioclip-2"
    assert meaning["ranking_revision"] == 4
    assert meaning["meaning_version"] == 1
    assert "margin" in meaning["score"].lower()
    assert "queue" in meaning["use"].lower()


def test_a_declared_meaning_says_what_the_score_is_not() -> None:
    meaning = score_meaning(model())
    stated = " ".join(meaning["not_meaning"]).lower()
    for claim in ["probability", "present", "absent", "model", "plant boundary"]:
        assert claim in stated, claim


def test_no_operating_point_or_abstention_rule_is_claimed() -> None:
    meaning = score_meaning(model())
    assert meaning["calibrated"] is False
    assert meaning["operating_point"] is None
    assert meaning["abstention"] is None
    rule = meaning["choosing_an_operating_point"].lower()
    assert "development" in rule and "before" in rule and "new meaning version" in rule


def test_runs_screened_before_model_choice_are_the_original_bioclip() -> None:
    legacy = model("bioclip")
    del legacy["model_key"]
    assert score_meaning(legacy)["id"] == "bioclip/ranking-4/meaning-1"


@pytest.mark.parametrize(
    "metadata",
    [
        None,
        {},
        model(ranking=3),
        model("bioclip", ranking=2),
        model() | {"revision": "a-different-checkpoint"},
        model() | {"calibrated": True},
    ],
)
def test_any_other_configuration_has_no_declared_meaning(metadata: dict | None) -> None:
    meaning = score_meaning(metadata)
    assert meaning["declared"] is False
    assert meaning["id"] is None
    assert meaning["evidence"] == []
    assert meaning["operating_point"] is None
    assert "within this run" in meaning["use"].lower()
    assert any("probability" in line.lower() for line in meaning["not_meaning"])


def test_meanings_are_returned_as_copies() -> None:
    score_meaning(model())["not_meaning"].append("tampered")
    assert "tampered" not in score_meaning(model())["not_meaning"]


@pytest.mark.parametrize("key", sorted({key for key, _ in DECLARED}))
def test_declared_evidence_matches_the_benchmark(key: str) -> None:
    """Every number a declaration cites is the benchmark's, so they cannot drift apart."""
    benchmark = json.loads((BENCHMARKS / "model-comparison.json").read_text())["models"][key]
    summary = benchmark["summary"]
    lookalikes = summary["lookalikes"].values()
    expected = {
        "references_own_target_top": tuple(summary["references_own_target_top"]),
        "incidental_positive_margin": (summary["incidental_positive"], summary["incidental_of"]),
        "lookalike_top_suggestion": (
            sum(row["top"] for row in lookalikes),
            sum(row["of"] for row in lookalikes),
        ),
        "lookalike_positive_margin": (
            sum(row["positive"] for row in lookalikes),
            sum(row["of"] for row in lookalikes),
        ),
    }
    meaning = score_meaning(model(key))
    assert benchmark["revision"] == meaning["model_revision"]
    cited = {item["key"]: (item["count"], item["of"]) for item in meaning["evidence"]}
    assert cited == expected
    for item in meaning["evidence"]:
        assert (Path(__file__).parents[1] / item["source"]).exists()
        assert "not expert" in item["labels"].lower()
        assert str(item["count"]) in item["finding"] and str(item["of"]) in item["finding"]


def test_the_export_and_detail_carry_the_run_meaning(tmp_path: Path) -> None:
    pilot(tmp_path)
    store = Store(tmp_path)
    store.model("run", model())
    exported = export(store, "run")["score_meaning"]
    assert exported["id"] == "bioclip-2/ranking-4/meaning-1"
    client = TestClient(create_app(tmp_path))
    assert client.get("/runs/run").json()["score_meaning"] == exported
    assert client.get("/runs/run/export").json()["score_meaning"] == exported


def test_an_unscreened_run_says_no_meaning_is_declared(tmp_path: Path) -> None:
    pilot(tmp_path)
    detail = TestClient(create_app(tmp_path)).get("/runs/run").json()
    assert detail["score_meaning"]["declared"] is False
