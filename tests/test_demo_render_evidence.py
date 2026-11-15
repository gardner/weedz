"""Rendered source pixels and attribution must come from the same produced snapshot."""

import hashlib
import importlib
import json
import sqlite3
import sys
from argparse import Namespace
from pathlib import Path

import pytest
from PIL import Image
from test_demo_snapshot import incomplete_source as incomplete_source
from test_demo_snapshot import script as snapshot_script

sys.path.insert(0, str(Path(__file__).parents[1] / "tools/demo-video"))
frames_module = importlib.import_module("demo_frames")
renderer = importlib.import_module("render_demo")


@pytest.fixture
def produced_captures(incomplete_source: Path, tmp_path: Path) -> Path:
    Image.new("RGB", (10, 10), "green").save(incomplete_source / "images/missing.png")
    with sqlite3.connect(incomplete_source / "discovery.sqlite3") as db:
        record, scores = db.execute("SELECT record,scores FROM photos").fetchone()
        record = json.loads(record)
        record["photo_id"] = 447484684
        db.execute("UPDATE photos SET record=?", (json.dumps(record),))
        bird = {**record, "photo_id": 460347209, "attribution": "Bird source creator"}
        db.execute(
            "INSERT INTO photos VALUES('bird','pilot',?,?,'unreviewed','','')",
            (json.dumps(bird), scores),
        )
    captures = tmp_path / "captures"
    snapshot_script.snapshot(incomplete_source, captures / "review-snapshot")
    return captures


def test_snapshot_is_the_only_producer_needed_for_rendered_source_photos(
    produced_captures, monkeypatch
):
    manifest = json.loads(
        (produced_captures / "review-snapshot/capture-provenance.json").read_text()
    )
    gorse = next(row for row in manifest["photos"] if row["file"] == "images/447484684.png")
    image = produced_captures / "review-snapshot/images/447484684.png"
    assert gorse["sha256"] == hashlib.sha256(image.read_bytes()).hexdigest()
    frames = frames_module.Frames(
        produced_captures, Path("unused"), 25, Path("unused"), Path("unused")
    )
    monkeypatch.setattr(frames_module, "text", lambda *_args, **_kwargs: None)
    assert frames.report_summary(0).size == (1920, 1080)
    assert not (produced_captures / "assets").exists()


def test_replaced_snapshot_pixels_are_refused_before_decode(produced_captures, monkeypatch):
    image = produced_captures / "review-snapshot/images/447484684.png"
    Image.new("RGB", (10, 10), "red").save(image)
    frames = frames_module.Frames(
        produced_captures, Path("unused"), 25, Path("unused"), Path("unused")
    )

    def no_decode(*_args, **_kwargs):
        pytest.fail("Unverified bytes must never reach the decoder")

    monkeypatch.setattr(Image, "open", no_decode)
    with pytest.raises(ValueError, match="checksum"):
        frames.image("review-snapshot/images/447484684.png")


def test_preflight_uses_snapshot_instead_of_undocumented_assets(produced_captures, tmp_path):
    mobile = tmp_path / "mobile"
    mobile.mkdir()
    for name in ["live-flutter-settings.webm", "live-settings-deleted.png"]:
        (mobile / name).touch()
    web = produced_captures / "web-final"
    web.mkdir()
    for name in [
        "web-review-interactions.webm",
        "web-reference-comparison.png",
        "web-candidate-window.png",
    ]:
        (web / name).touch()
    credit_font = tmp_path / "font.otf"
    credit_font.touch()
    renderer.validate_captures(
        Namespace(captures=produced_captures, mobile_captures=mobile, credit_font=credit_font)
    )
