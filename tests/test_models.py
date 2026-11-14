"""Screening models are declared and pinned, and each run says which one it uses."""

import hashlib
from pathlib import Path

import pytest
from pydantic import ValidationError
from test_discovery import observation
from test_discovery_inference import FakeEncoder

from weedz.discovery.activities import Activities
from weedz.discovery.inference import MODELS, Screener
from weedz.discovery.records import RunSpec
from weedz.discovery.source import photo_from_observation


def test_registry_pins_every_model_to_a_full_revision() -> None:
    assert {"bioclip", "bioclip-2"} <= set(MODELS)
    for entry in MODELS.values():
        assert len(entry["revision"]) == 40
        assert entry["weights"].endswith((".bin", ".safetensors"))
    assert MODELS["bioclip"]["revision"].startswith("ce901ab3")


def test_metadata_names_the_screening_model() -> None:
    def make(key: str) -> Screener:
        return Screener(
            FakeEncoder(), lambda _i: None, lambda p: p, "hash", preprocessing={}, model_key=key
        )

    assert make("bioclip-2").metadata["model"] == MODELS["bioclip-2"]["repo"]
    assert make("bioclip-2").metadata["model_key"] == "bioclip-2"
    assert make("bioclip").metadata["revision"] == MODELS["bioclip"]["revision"]


def test_run_spec_rejects_unknown_models() -> None:
    assert RunSpec(model="bioclip-2").model == "bioclip-2"
    with pytest.raises(ValidationError):
        RunSpec.model_validate({"model": "resnet"})


def test_screening_uses_the_run_model(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    activities = Activities(tmp_path)
    activities.store.create_run("run", RunSpec(model="bioclip-2"))
    photo = photo_from_observation(observation(), "Nelson", "incidental")
    assert photo is not None
    photo.image_path = "image.jpg"
    (tmp_path / photo.image_path).write_bytes(b"image")
    photo.sha256 = hashlib.sha256(b"image").hexdigest()
    activities.store.save_photos("run", [photo])
    loaded: list[str] = []

    class FakeScreener:
        metadata = {"model_key": "bioclip-2"}

        def screen(self, _path: Path, _subject: str | None = None) -> dict:
            return {"similarity": 0.1}

    def load(_cache: Path, model: str) -> FakeScreener:
        loaded.append(model)
        return FakeScreener()

    monkeypatch.setattr("weedz.discovery.inference.Screener.load", load)
    monkeypatch.setattr("weedz.discovery.activities.activity.heartbeat", lambda *_: None)
    activities.screen_photos({"run_id": "run"})
    assert loaded == ["bioclip-2"]


def test_comparison_summarises_pilot_and_lookalike_behaviour() -> None:
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "compare_models", Path(__file__).parents[1] / "scripts" / "compare_models.py"
    )
    assert spec and spec.loader
    compare = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(compare)
    rows = [
        {
            "cohort": "incidental",
            "best_species": "Ulex europaeus",
            "margins": {"Ulex europaeus": 0.1},
        },
        {
            "cohort": "incidental",
            "best_species": "Ulex europaeus",
            "margins": {"Ulex europaeus": -0.1},
        },
        {
            "cohort": "reference",
            "reference_species": "Ulex europaeus",
            "best_species": "Ulex europaeus",
            "margins": {"Ulex europaeus": 0.2},
        },
        {
            "cohort": "lookalike",
            "lookalike_taxon": "Austroderia",
            "lookalike_of": "Cortaderia selloana",
            "best_species": "Cortaderia selloana",
            "margins": {"Cortaderia selloana": 0.03},
        },
    ]
    summary = compare.summarise(rows, seconds=4.0)
    assert summary["incidental_positive"] == 1
    assert summary["references_own_target_top"] == [1, 1]
    assert summary["lookalikes"]["Austroderia"] == {"top": 1, "positive": 1, "of": 1}
    assert summary["seconds_per_photo"] == 1.0


def test_discover_accepts_a_model() -> None:
    from weedz.discovery import cli as discovery_cli

    assert discovery_cli.parse(["discover", "--model", "bioclip-2"]).model == "bioclip-2"
    assert discovery_cli.parse(["discover"]).model == "bioclip-2"


def test_new_runs_default_to_bioclip_2_but_saved_runs_keep_bioclip() -> None:
    assert RunSpec().model == "bioclip-2"
    saved = {"limit_per_region": 12, "controls_per_species": 1, "before": "2024-12-31"}
    assert RunSpec.from_saved(saved).model == "bioclip"
    assert RunSpec.from_saved(saved | {"model": "bioclip-2"}).model == "bioclip-2"


def test_a_legacy_bioclip_run_resumes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    activities = Activities(tmp_path)
    activities.store.create_run("run", RunSpec(model="bioclip"))
    with activities.store.connect() as db:  # a run saved before model choice existed
        db.execute(
            "UPDATE runs SET spec=? WHERE id='run'",
            ('{"limit_per_region": 12, "controls_per_species": 1, "before": "2024-12-31"}',),
        )
    legacy = {"model": MODELS["bioclip"]["repo"], "revision": MODELS["bioclip"]["revision"]}
    activities.store.model("run", legacy)

    class FakeScreener:
        metadata = legacy | {"model_key": "bioclip"}

        def screen(self, _path: Path, _subject: str | None = None) -> dict:
            return {}

    loaded: list[str] = []

    def load(_cache: Path, model: str) -> FakeScreener:
        loaded.append(model)
        return FakeScreener()

    monkeypatch.setattr("weedz.discovery.inference.Screener.load", load)
    monkeypatch.setattr("weedz.discovery.activities.activity.heartbeat", lambda *_: None)
    activities.screen_photos({"run_id": "run"})
    assert loaded == ["bioclip"]


def test_comparison_document_matches_the_committed_benchmark_shape() -> None:
    import importlib.util
    import json

    spec = importlib.util.spec_from_file_location(
        "compare_models", Path(__file__).parents[1] / "scripts" / "compare_models.py"
    )
    assert spec and spec.loader
    compare = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(compare)
    row = {
        "id": "a",
        "cohort": "reference",
        "reference_species": "Ulex europaeus",
        "best_species": "Ulex europaeus",
        "margins": {"Ulex europaeus": 0.2},
    }
    results = {
        "bioclip-2": {
            "metadata": {
                "model": "m",
                "model_key": "bioclip-2",
                "revision": "r",
                "weights_sha256": "w",
                "prompts": ["x"],
            },
            "summary": {"x": 1},
            "rows": [row],
        }
    }
    document = compare.document(results, "2026-11-14")
    committed = json.loads(
        (Path(__file__).parents[1] / "benchmarks" / "model-comparison.json").read_text()
    )
    assert set(document) == set(committed)
    entry = document["models"]["bioclip-2"]
    assert set(entry) == set(committed["models"]["bioclip-2"])
    assert entry["reference_own_target_margins"] == [0.2]
    assert set(entry["rows"][0]) == set(committed["models"]["bioclip-2"]["rows"][0])
