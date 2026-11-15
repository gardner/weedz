"""Real-app capture uploads must use the licensed source bytes associated with its score."""

import base64
import hashlib
import importlib.util
import io
import json
import sqlite3
from pathlib import Path

import pytest
from PIL import Image

spec = importlib.util.spec_from_file_location(
    "demo_public_report", Path(__file__).parents[1] / "scripts/demo_public_report.py"
)
assert spec and spec.loader
report = importlib.util.module_from_spec(spec)
spec.loader.exec_module(report)


@pytest.fixture
def public_pilot(tmp_path: Path) -> Path:
    (tmp_path / "images").mkdir()
    image = tmp_path / "images/public.png"
    exif = Image.Exif()
    exif[0x010E] = "source metadata must not travel"
    Image.new("RGB", (6, 8), "green").save(image, exif=exif)
    record = {
        "photo_license": "cc-by",
        "image_path": "images/public.png",
        "sha256": hashlib.sha256(image.read_bytes()).hexdigest(),
        "attribution": "Public source creator",
    }
    with sqlite3.connect(tmp_path / "discovery.sqlite3") as db:
        db.execute("CREATE TABLE runs(id TEXT,status TEXT,model TEXT)")
        db.execute("CREATE TABLE photos(id TEXT,run_id TEXT,record TEXT,scores TEXT)")
        db.execute(
            "INSERT INTO runs VALUES(?, 'completed', ?)",
            (
                report.SOURCE_RUN,
                json.dumps(
                    {
                        "model": "imageomics/bioclip",
                        "revision": "ce901ab3c6a913f9e9ef94ce6d27761069f4f01c",
                        "ranking_revision": 2,
                    }
                ),
            ),
        )
        db.execute(
            "INSERT INTO photos VALUES(?,?,?,?)",
            (
                report.SOURCE_PHOTO,
                report.SOURCE_RUN,
                json.dumps(record),
                json.dumps({"best_species": "Ulex europaeus", "margin": 0.12}),
            ),
        )
    return tmp_path


def test_report_derives_attribution_model_and_clean_image_from_checked_source(
    public_pilot: Path,
) -> None:
    result = report.source_report(public_pilot)
    assert result["consent"]["credit"] == "Public source creator"
    assert result["candidate"] == {"taxon": "Ulex europaeus", "score": 0.12}
    assert result["model"]["model_key"] == "bioclip"
    with Image.open(io.BytesIO(base64.b64decode(result["image"]))) as photo:
        assert photo.size == (6, 8)
        assert not photo.getexif()


def test_replaced_cached_image_cannot_inherit_the_source_credit(public_pilot: Path) -> None:
    Image.new("RGB", (6, 8), "red").save(public_pilot / "images/public.png")
    with pytest.raises(ValueError, match="checksum"):
        report.source_report(public_pilot)


def test_cache_path_cannot_point_at_an_unrelated_file(public_pilot: Path) -> None:
    with sqlite3.connect(public_pilot / "discovery.sqlite3") as db:
        record = json.loads(db.execute("SELECT record FROM photos").fetchone()[0])
        record["image_path"] = "../private.png"
        db.execute("UPDATE photos SET record=?", (json.dumps(record),))
    with pytest.raises(ValueError, match="public image cache"):
        report.source_report(public_pilot)
