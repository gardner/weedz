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


def test_seed_preserves_source_run_creation_time(tmp_path):
    source = source_store(tmp_path / "source")
    timestamp = "2024-01-02T03:04:05+00:00"
    with sqlite3.connect(source.database) as db:
        db.execute("UPDATE runs SET created_at=?", (timestamp,))
    output = tmp_path / "site"
    script.seed(source.root, output, "source")
    assert Store(output).runs()[0]["created_at"] == timestamp


@pytest.mark.parametrize("mixed", [False, True])
def test_hosting_policy_refuses_scored_noncommercial_photos_without_partial_output(tmp_path, mixed):
    source = source_store(tmp_path / "source")
    with sqlite3.connect(source.database) as db:
        run_id, photo_id, raw, scores = db.execute(
            "SELECT run_id,id,record,scores FROM photos"
        ).fetchone()
        record = json.loads(raw)
        record["photo_license"] = "cc-by-nc"
        if mixed:
            record["id"] = "noncommercial-copy"
            db.execute(
                "INSERT INTO photos(run_id,id,record,scores) VALUES(?,?,?,?)",
                (run_id, record["id"], json.dumps(record), scores),
            )
        else:
            db.execute("UPDATE photos SET record=? WHERE id=?", (json.dumps(record), photo_id))
    output = tmp_path / "site"
    with pytest.raises(ValueError, match="1 scored photo.*cc-by-nc"):
        script.seed(source.root, output, "source")
    assert not output.exists()
