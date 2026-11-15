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
    (web / "web-capture.json").write_text(
        json.dumps(
            {
                "browserErrors": [],
                "captureSuccess": True,
                "media_sha256": {
                    name: hashlib.sha256((web / name).read_bytes()).hexdigest()
                    for name in renderer.WEB_MEDIA
                },
            }
        )
    )
    credit_font = tmp_path / "font.otf"
    credit_font.write_bytes(Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf").read_bytes())
    (mobile / "erasure-verification.json").write_text(
        json.dumps(
            {
                "capture_instance": "test-instance",
                "active_report_bodies_after_real_app_deletion": 0,
                "remaining_crop_files": 0,
            }
        )
    )
    (mobile / "live-capture.json").write_text(
        json.dumps(
            {
                "captureSuccess": True,
                "browser_errors": [],
                "capture_instance": "test-instance",
                "report_created_via_real_api": 201,
                "stable_deletion_status": 200,
                "upload_after_deletion": 401,
                "media_sha256": {
                    name: hashlib.sha256((mobile / name).read_bytes()).hexdigest()
                    for name in renderer.MOBILE_MEDIA
                },
            }
        )
    )
    renderer.validate_captures(
        Namespace(captures=produced_captures, mobile_captures=mobile, credit_font=credit_font)
    )
    (mobile / "erasure-verification.json").unlink()
    with pytest.raises(ValueError, match="erasure"):
        renderer.validate_captures(
            Namespace(captures=produced_captures, mobile_captures=mobile, credit_font=credit_font)
        )


@pytest.mark.parametrize(
    "proof",
    [
        None,
        {},
        [],
        {"active_report_bodies_after_real_app_deletion": False, "remaining_crop_files": 0},
        {"active_report_bodies_after_real_app_deletion": 1, "remaining_crop_files": 0},
        {"active_report_bodies_after_real_app_deletion": 0, "remaining_crop_files": 1},
    ],
)
def test_failed_or_unverified_mobile_erasure_is_not_renderable(produced_captures, tmp_path, proof):
    mobile = tmp_path / "mobile"
    mobile.mkdir()
    if proof is not None:
        (mobile / "erasure-verification.json").write_text(json.dumps(proof))
    with pytest.raises(ValueError, match="erasure"):
        renderer.validate_erasure(mobile)


@pytest.mark.parametrize(
    "proof", [None, {}, [], {"browserErrors": ["Script failed"]}, {"browserErrors": ""}]
)
def test_failed_browser_capture_is_not_renderable(tmp_path, proof):
    if proof is not None:
        (tmp_path / "web-capture.json").write_text(json.dumps(proof))
    with pytest.raises(ValueError, match="browser"):
        renderer.validate_browser_capture(tmp_path)


@pytest.mark.parametrize(
    "change",
    [
        {"captureSuccess": False},
        {"browser_errors": ["Uncaught app failure"]},
        {"browser_errors": None},
        {"report_created_via_real_api": 200},
        {"stable_deletion_status": 500},
        {"upload_after_deletion": 201},
    ],
)
def test_mobile_capture_requires_closed_error_free_real_api_evidence(tmp_path, change):
    proof = {
        "captureSuccess": True,
        "browser_errors": [],
        "report_created_via_real_api": 201,
        "stable_deletion_status": 200,
        "upload_after_deletion": 401,
    }
    (tmp_path / "live-capture.json").write_text(json.dumps(proof | change))
    with pytest.raises(ValueError, match="Mobile browser capture"):
        renderer.validate_mobile_capture(tmp_path)


def test_missing_mobile_capture_receipt_is_not_renderable(tmp_path):
    with pytest.raises(ValueError, match="Mobile browser capture"):
        renderer.validate_mobile_capture(tmp_path)


def test_replaced_capture_media_cannot_inherit_success(tmp_path):
    hashes = {}
    for name in renderer.WEB_MEDIA:
        (tmp_path / name).write_bytes(b"original")
        hashes[name] = hashlib.sha256(b"original").hexdigest()
    (tmp_path / "web-capture.json").write_text(
        json.dumps({"captureSuccess": True, "browserErrors": [], "media_sha256": hashes})
    )
    renderer.validate_browser_capture(tmp_path)
    (tmp_path / renderer.WEB_MEDIA[0]).write_bytes(b"replacement valid video")
    with pytest.raises(ValueError, match="checksum"):
        renderer.validate_browser_capture(tmp_path)


def test_frames_read_private_verified_capture_instead_of_replaced_original(
    produced_captures, tmp_path
):
    web = produced_captures / "web-final"
    web.mkdir()
    checked = tmp_path / "verified-web"
    checked.mkdir()
    name = "web-reference-comparison.png"
    Image.new("RGB", (3, 3), "green").save(checked / name)
    Image.new("RGB", (3, 3), "red").save(web / name)
    frames = frames_module.Frames(
        produced_captures, Path("unused"), 25, Path("unused"), Path("unused"), checked
    )
    assert frames.image("web-final/" + name).getpixel((0, 0)) == (0, 128, 0)


def test_snapshot_uses_the_same_validated_receipt_after_receipt_replacement(tmp_path):
    hashes = {}
    for name in renderer.WEB_MEDIA:
        (tmp_path / name).write_bytes(b"original")
        hashes[name] = hashlib.sha256(b"original").hexdigest()
    receipt = tmp_path / "web-capture.json"
    receipt.write_text(
        json.dumps({"captureSuccess": True, "browserErrors": [], "media_sha256": hashes})
    )
    validated = renderer.validate_browser_capture(tmp_path)
    for name in renderer.WEB_MEDIA:
        (tmp_path / name).write_bytes(b"unrelated replacement")
    receipt.write_text(
        json.dumps(
            {
                "captureSuccess": False,
                "media_sha256": {
                    name: hashlib.sha256(b"unrelated replacement").hexdigest()
                    for name in renderer.WEB_MEDIA
                },
            }
        )
    )
    private = tmp_path / "private"
    private.mkdir()
    with pytest.raises(ValueError, match="checksum"):
        renderer.checked_files(tmp_path, renderer.WEB_MEDIA, validated["media_sha256"], private)


def test_replaced_mobile_media_cannot_inherit_real_deletion_receipt(tmp_path):
    hashes = {}
    for name in renderer.MOBILE_MEDIA:
        (tmp_path / name).write_bytes(b"original app recording")
        hashes[name] = hashlib.sha256(b"original app recording").hexdigest()
    (tmp_path / "live-capture.json").write_text(
        json.dumps(
            {
                "captureSuccess": True,
                "browser_errors": [],
                "media_sha256": hashes,
                "capture_instance": "test-instance",
                "report_created_via_real_api": 201,
                "stable_deletion_status": 200,
                "upload_after_deletion": 401,
            }
        )
    )
    renderer.validate_mobile_capture(tmp_path)
    (tmp_path / renderer.MOBILE_MEDIA[0]).write_bytes(b"unrelated valid app video")
    with pytest.raises(ValueError, match="checksum"):
        renderer.validate_mobile_capture(tmp_path)


@pytest.mark.parametrize("erased,recorded", [("old", "new"), (None, None), ("", "")])
def test_erasure_and_recording_must_belong_to_the_same_real_capture(erased, recorded):
    with pytest.raises(ValueError, match="capture instance"):
        renderer.validate_capture_instances(
            {"capture_instance": erased}, {"capture_instance": recorded}
        )
