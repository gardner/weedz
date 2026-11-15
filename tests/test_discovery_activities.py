import hashlib
import json
from pathlib import Path

import pytest
from test_discovery import observation

from weedz.discovery.activities import Activities
from weedz.discovery.records import RunSpec
from weedz.discovery.source import photo_from_observation


def test_retry_refuses_to_mix_scoring_configurations(tmp_path: Path, monkeypatch) -> None:
    activities = Activities(tmp_path)
    activities.store.create_run("run", RunSpec())
    photo = photo_from_observation(observation(), "Nelson", "incidental")
    assert photo is not None
    photo.image_path = "image.jpg"
    path = tmp_path / photo.image_path
    path.write_bytes(b"test image")
    photo.sha256 = hashlib.sha256(path.read_bytes()).hexdigest()
    activities.store.save_photos("run", [photo])
    activities.store.model("run", {"revision": "old"})
    activities.store.score("run", photo.id, {"similarity": 0.2})

    class FakeScreener:
        metadata = {"revision": "changed"}

    activities.screeners[RunSpec().model] = FakeScreener()
    monkeypatch.setattr("weedz.discovery.activities.activity.heartbeat", lambda *_: None)
    with pytest.raises(ValueError, match="configuration changed"):
        activities.screen_photos({"run_id": "run"})
    assert activities.store.runs()[0]["model"] == {"revision": "old"}


def test_failed_manifest_write_is_not_reported_as_completed(tmp_path: Path, monkeypatch) -> None:
    activities = Activities(tmp_path)
    activities.store.create_run("run", RunSpec())
    monkeypatch.setattr("weedz.discovery.activities.activity.heartbeat", lambda *_: None)

    def fail(*_args):
        raise OSError("Disk write failed")

    monkeypatch.setattr(Path, "replace", fail)
    with pytest.raises(OSError, match="Disk write failed"):
        activities.export_run({"run_id": "run"})
    assert activities.store.runs()[0]["status"] != "completed"


def test_completion_manifest_suitability_reads_the_run_as_completed(
    tmp_path: Path, monkeypatch
) -> None:
    activities = Activities(tmp_path)
    activities.store.create_run("run", RunSpec())
    photo = photo_from_observation(observation(), "Nelson", "incidental")
    assert photo is not None
    activities.store.save_photos("run", [photo])
    monkeypatch.setattr("weedz.discovery.activities.activity.heartbeat", lambda *_: None)
    manifest = Path(activities.export_run({"run_id": "run"})["manifest"])
    scope = json.loads(manifest.read_text())["source_suitability"]["scope"]
    assert scope["run_status"] == "completed"
    assert not any("The run is" in gap for gap in scope["gaps"])


def test_screening_passes_each_photo_original_subject(tmp_path: Path, monkeypatch) -> None:
    activities = Activities(tmp_path)
    activities.store.create_run("run", RunSpec())
    photo = photo_from_observation(observation(), "Nelson", "incidental")
    assert photo is not None
    photo.image_path = "image.jpg"
    path = tmp_path / photo.image_path
    path.write_bytes(b"test image")
    photo.sha256 = hashlib.sha256(path.read_bytes()).hexdigest()
    activities.store.save_photos("run", [photo])
    subjects: list[str | None] = []

    class FakeScreener:
        metadata = {"revision": "same"}

        def screen(self, _path: Path, subject: str | None = None) -> dict:
            subjects.append(subject)
            return {"similarity": 0.1}

    activities.screeners[RunSpec().model] = FakeScreener()
    monkeypatch.setattr("weedz.discovery.activities.activity.heartbeat", lambda *_: None)
    activities.screen_photos({"run_id": "run"})
    assert subjects == [f"{photo.original_taxon}, {photo.original_common_name}"]


def test_gpu_run_does_not_reuse_preloaded_cpu_encoder(tmp_path, monkeypatch):
    from types import SimpleNamespace

    from weedz.discovery.inference import Screener

    activities = Activities(tmp_path)
    activities.store.create_run("run", RunSpec(screening_backend="cuda-fp32-v1"))
    activities.screeners["bioclip-2"] = SimpleNamespace(metadata={"device": "cpu"})
    calls = []
    gpu = SimpleNamespace(
        metadata={"model_key": "bioclip-2", "device": "cuda:0", "backend_profile": "cuda-fp32-v1"}
    )

    def load(cache, *, model, backend):
        calls.append((model, backend))
        return gpu

    monkeypatch.setattr(Screener, "load", load)
    monkeypatch.setattr("weedz.discovery.activities.activity.heartbeat", lambda *_: None)
    monkeypatch.setattr("weedz.discovery.activities.while_heartbeating", lambda fn, *_: fn())
    assert activities._screener("run") is gpu
    assert activities._screener("run") is gpu
    assert calls == [("bioclip-2", "cuda-fp32-v1")]
    assert activities.store.runs()[0]["model"]["score_meaning"] is None
