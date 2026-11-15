"""Website seeding copies licensed pixels/evidence, never private source state."""

import hashlib
import importlib.util
import json
import sqlite3
from pathlib import Path

import pytest
from PIL import Image
from test_discovery import observation

from weedz.discovery.records import RunSpec
from weedz.discovery.source import photo_from_observation
from weedz.discovery.store import Store

_spec = importlib.util.spec_from_file_location(
    "site_seed", Path(__file__).parents[1] / "scripts/seed_review_site.py"
)
assert _spec and _spec.loader
script = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(script)


def source_store(root: Path) -> Store:
    store = Store(root)
    store.create_run("source", RunSpec())
    store.model("source", {"proposal_experiment": {"class_agnostic": True}})
    photo = photo_from_observation(observation(), "Nelson", "incidental")
    assert photo
    image = root / "images/source.png"
    image.parent.mkdir()
    Image.new("RGB", (8, 8)).save(image)
    photo.photo_license = "cc-by"
    photo.observation_license = "cc-by"
    photo.image_path = "images/source.png"
    photo.sha256 = hashlib.sha256(image.read_bytes()).hexdigest()
    photo.latitude, photo.longitude, photo.positional_accuracy_m = 12.3456789, 98.7654321, 4
    store.save_photos("source", [photo])
    store.score(
        "source", photo.id, {"margin": 0.12, "segmentation": {"status": "ok", "regions": []}}
    )
    store.review("source", photo.id, "confirmed", "Private reviewer", "Private note")
    store.status("source", "completed", "source")
    return store


def test_seed_retains_real_evidence_without_private_coordinates_or_history(tmp_path):
    source = source_store(tmp_path / "source")
    before = source.database.read_bytes()
    output = tmp_path / "site"
    assert script.seed(source.root, output, "source") == 1
    assert source.database.read_bytes() == before
    assert Store(output).runs()[0]["model"] == source.runs()[0]["model"]
    assert Store(output).photos("source")[0]["scores"] == source.photos("source")[0]["scores"]
    with sqlite3.connect(output / "discovery.sqlite3") as db:
        record, scores, status, note = db.execute(
            "SELECT record,scores,review_status,review_note FROM photos"
        ).fetchone()
        assert json.loads(record)["latitude"] is None
        assert json.loads(scores)["margin"] == 0.12
        assert (status, note) == ("unreviewed", "")
    raw = (output / "discovery.sqlite3").read_bytes()
    assert b"Private note" not in raw and b"12.3456789" not in raw
    assert not (output / "access.sqlite3").exists()


def test_bad_image_provenance_never_publishes_a_site(tmp_path):
    source = source_store(tmp_path / "source")
    (source.root / "images/source.png").write_bytes(b"different image")
    output = tmp_path / "site"
    with pytest.raises(ValueError, match="provenance"):
        script.seed(source.root, output, "source")
    assert not output.exists()


@pytest.mark.parametrize("timestamp", ["2025-03-04T05:06:07+00:00", None])
def test_seed_preserves_original_screening_timestamp(tmp_path, timestamp):
    source = source_store(tmp_path / "source")
    with sqlite3.connect(source.database) as db:
        db.execute("UPDATE photos SET screened_at=?", (timestamp,))
    output = tmp_path / "site"
    script.seed(source.root, output, "source")
    with sqlite3.connect(output / "discovery.sqlite3") as db:
        assert db.execute("SELECT screened_at FROM photos").fetchone()[0] == timestamp
