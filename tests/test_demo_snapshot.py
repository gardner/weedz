"""Demo copies retain real scores but cannot disclose source coordinates or mutate reviews."""

import hashlib
import importlib.util
import json
import sqlite3
from pathlib import Path

import pytest
from PIL import Image

SPEC = importlib.util.spec_from_file_location(
    "capture_demo_snapshot", Path(__file__).parents[1] / "scripts/capture_demo_snapshot.py"
)
assert SPEC is not None and SPEC.loader is not None
script = importlib.util.module_from_spec(SPEC)
with pytest.MonkeyPatch.context() as import_path:
    import_path.syspath_prepend(str(Path(__file__).parents[1] / "scripts"))
    SPEC.loader.exec_module(script)


def test_snapshot_does_not_write_live_source_and_erases_coordinates_from_copy(
    tmp_path: Path,
) -> None:
    source, target = tmp_path / "live", tmp_path / "capture"
    (source / "images").mkdir(parents=True)
    Image.new("RGB", (10, 10), "green").save(source / "images/1.jpg")
    record = {
        "photo_id": 1,
        "photo_license": "cc-by",
        "image_path": "images/1.jpg",
        "attribution": "Example public creator, CC BY",
        "source_url": "https://example.test/observation/1",
        "image_url": "https://example.test/photo/1.jpg",
        "cohort": "incidental",
        "latitude": 12.3456789,
        "longitude": 12.3456789,
    }
    scores = {"margin": 0.123, "box": [0, 0, 10, 10]}
    database = source / "discovery.sqlite3"
    with sqlite3.connect(database) as db:
        db.executescript("""
            CREATE TABLE runs(id TEXT,status TEXT,created_at TEXT,detail TEXT);
            CREATE TABLE photos(id TEXT,run_id TEXT,record TEXT,scores TEXT,
                review_status TEXT,review_note TEXT,review_reviewer TEXT);
            CREATE TABLE reviews(note TEXT);
        """)
        db.execute("INSERT INTO runs VALUES('pilot','completed','2026-01-01','original')")
        db.execute(
            "INSERT INTO photos VALUES('p','pilot',?,?,'confirmed','Private note','Reviewer')",
            (json.dumps(record), json.dumps(scores)),
        )
        db.execute("INSERT INTO reviews VALUES('private live decision')")
    before = hashlib.sha256(database.read_bytes()).hexdigest()
    result = script.snapshot(source, target)
    assert hashlib.sha256(database.read_bytes()).hexdigest() == before
    with sqlite3.connect(target / "discovery.sqlite3") as copied:
        row = copied.execute(
            "SELECT record,scores,review_status,review_note FROM photos"
        ).fetchone()
        assert json.loads(row[0])["latitude"] is None
        assert json.loads(row[1]) == scores
        assert row[2:] == ("unreviewed", "")
        assert copied.execute("SELECT COUNT(*) FROM reviews").fetchone()[0] == 0
    assert "12.3456789" not in json.dumps(result)
    assert b"12.3456789" not in (target / "discovery.sqlite3").read_bytes()
    assert "Private note" not in (target / "discovery.sqlite3").read_bytes().decode(errors="ignore")
    with Image.open(target / "images/1.png") as image:
        assert not image.getexif()
