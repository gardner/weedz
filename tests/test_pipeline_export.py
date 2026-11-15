"""Manifest completion distinguishes stage failures from a successful SAM analysis."""

import json

import pytest
from test_segmentation_stages import Proposer, runner
from test_segmentation_stages import store as store

from weedz.discovery.activities import Activities, export
from weedz.discovery.records import RunSpec


def test_baseline_export_keeps_historical_no_segmentation_limit(tmp_path):
    activities = Activities(tmp_path)
    activities.store.create_run("baseline", RunSpec())
    result = export(activities.store, "baseline")
    assert "pipeline" not in result
    assert "no segmentation model used" in result["limitations"][1]


def test_missing_stages_prevent_a_successful_completion_manifest(store, monkeypatch):
    monkeypatch.setattr("weedz.discovery.activities.activity.heartbeat", lambda *_: None)
    with pytest.raises(ValueError, match="stages have not completed"):
        Activities(store.root).export_run({"run_id": "run"})
    assert not (store.root / "runs/run/manifest.json").exists()
    assert store.runs()[0]["status"] != "completed"


def test_partial_fallback_is_declared_in_manifest_and_run_detail(store, monkeypatch):
    monkeypatch.setattr("weedz.discovery.activities.activity.heartbeat", lambda *_: None)
    stages = runner(store, Proposer(), 3)
    stages.segment("run")
    for photo in store.photos("run"):
        store.score("run", photo["id"], {"margin": 0.1})
    monkeypatch.setattr(
        "weedz.segmentation.stages.identify_views",
        lambda _model, views, _subject: {name: {"margin": -0.2} for name in views},
    )
    stages.score_regions("run")
    result = Activities(store.root).export_run({"run_id": "run"})
    manifest = json.loads((store.root / "runs/run/manifest.json").read_text())
    assert result["pipeline_outcome"] == "partial"
    assert manifest["pipeline"]["failed"] == 1
    assert manifest["pipeline"]["warnings"]
    assert "fallback" in manifest["run"]["detail"]
    assert "no segmentation model used" not in manifest["limitations"][1]
