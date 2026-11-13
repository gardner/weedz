import hashlib
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

    activities.screener = FakeScreener()
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
