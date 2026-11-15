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
        "observation_license": "cc-by-nc",
        "observer": "Actual observer",
        "source_url": "https://example.test/observations/1",
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


def test_capture_provenance_binds_actual_uploaded_image_and_its_own_rights(public_pilot):
    captured = report.source_capture(public_pilot)
    image = base64.b64decode(captured["report"]["image"])
    provenance = captured["source_provenance"]
    assert provenance["report_image_sha256"] == hashlib.sha256(image).hexdigest()
    assert (
        provenance["source_image_sha256"]
        == hashlib.sha256((public_pilot / "images/public.png").read_bytes()).hexdigest()
    )
    assert provenance["rights"]["attribution"] == "Public source creator"
    assert provenance["rights"]["observation_licence"] == "cc-by-nc"
    assert "JPEG" in provenance["modifications"]


def test_same_photo_id_in_two_pilots_keeps_each_actual_credit_and_bytes(
    public_pilot, tmp_path_factory
):
    import shutil

    other = tmp_path_factory.mktemp("other-mobile-source")
    shutil.copytree(public_pilot, other, dirs_exist_ok=True)
    Image.new("RGB", (6, 8), "red").save(other / "images/public.png")
    with sqlite3.connect(other / "discovery.sqlite3") as db:
        record = json.loads(db.execute("SELECT record FROM photos").fetchone()[0])
        record.update(
            attribution="Different source photographer",
            observation_license="cc0",
            sha256=hashlib.sha256((other / "images/public.png").read_bytes()).hexdigest(),
        )
        db.execute("UPDATE photos SET record=?", (json.dumps(record),))
    first = report.source_capture(public_pilot)["source_provenance"]
    second = report.source_capture(other)["source_provenance"]
    assert first["source_photo_id"] == second["source_photo_id"]
    assert first["rights"]["attribution"] == "Public source creator"
    assert second["rights"]["attribution"] == "Different source photographer"
    assert second["rights"]["observation_licence"] == "cc0"
    assert first["source_image_sha256"] != second["source_image_sha256"]
    assert first["report_image_sha256"] != second["report_image_sha256"]
