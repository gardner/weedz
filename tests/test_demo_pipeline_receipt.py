"""The website film requires a closed error-free capture, not merely existing footage."""

import importlib
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parents[1] / "tools/demo-video"))


@pytest.mark.parametrize(
    "proof",
    [
        None,
        {},
        [],
        {"captureSuccess": False, "browser_errors": []},
        {"captureSuccess": True, "browser_errors": ["Uncaught application error"]},
    ],
)
def test_v3_refuses_failed_or_unclosed_pipeline_capture(tmp_path, proof):
    renderer = importlib.import_module("render_web_demo")
    if proof is not None:
        (tmp_path / "capture-manifest.json").write_text(json.dumps(proof))
    with pytest.raises(ValueError, match="Pipeline browser capture"):
        renderer.validate_pipeline_capture(tmp_path)


def completed_pipeline(tmp_path):
    import hashlib

    renderer = importlib.import_module("render_web_demo")
    for name in renderer.PIPELINE_MEDIA:
        (tmp_path / name).write_bytes(name.encode())
    source_hash = hashlib.sha256((tmp_path / "source-reference.png").read_bytes()).hexdigest()
    model = {"model": "fixture classifier", "revision": "fixture revision"}
    segmentation = {"model": "fixture proposer", "revision": "fixture revision"}
    photo = {
        "id": "expected-gorse",
        "photo_id": 447484684,
        "sha256": source_hash,
        "attribution": "Source credit",
        "observer": "Actual source observer",
        "photo_license": "cc-by",
        "observation_license": "cc-by-nc",
        "source_url": "https://example.test/source",
        "scores": {"segmentation": {"provenance": segmentation}},
    }
    (tmp_path / "model-evidence.json").write_text(
        json.dumps({"run_id": "segmentation-experiment-v1", "photo": photo, "model": model})
    )
    hashes = {
        name: hashlib.sha256((tmp_path / name).read_bytes()).hexdigest()
        for name in renderer.PIPELINE_MEDIA
    }
    proof = {
        "captureSuccess": True,
        "browser_errors": [],
        "media_sha256": hashes,
        "baseline": model,
        "segmentation": segmentation,
        "selection": {
            "run_id": "segmentation-experiment-v1",
            "photo_id": photo["id"],
            "source_photo_id": photo["photo_id"],
        },
        "source": {
            "creator": "Source credit",
            "observer": "Actual source observer",
            "licence": "cc-by",
            "observation_licence": "cc-by-nc",
            "source_url": "https://example.test/source",
            "source_image_sha256": source_hash,
        },
    }
    (tmp_path / "capture-manifest.json").write_text(json.dumps(proof))
    return proof


def test_v3_accepts_a_closed_error_free_capture_receipt(tmp_path):
    renderer = importlib.import_module("render_web_demo")
    proof = completed_pipeline(tmp_path)
    assert renderer.validate_pipeline_capture(tmp_path) == proof


def test_v3_refuses_replaced_pipeline_media(tmp_path):
    import hashlib

    renderer = importlib.import_module("render_web_demo")
    name = "original-ui.png"
    (tmp_path / name).write_bytes(b"original captured bytes")
    proof = {
        "captureSuccess": True,
        "browser_errors": [],
        "media_sha256": {name: hashlib.sha256(b"original captured bytes").hexdigest()},
    }
    (tmp_path / "capture-manifest.json").write_text(json.dumps(proof))
    (tmp_path / name).write_bytes(b"unrelated replacement")
    with pytest.raises(ValueError, match="checksum"):
        renderer.validate_pipeline_capture(tmp_path)


def test_v3_bad_ui_font_is_rejected_before_output_creation(tmp_path):
    from argparse import Namespace

    renderer = importlib.import_module("render_web_demo")
    output = tmp_path / "unpublished"
    with pytest.raises(ValueError, match="ui-font"):
        renderer.render(Namespace(output=output, ui_font=tmp_path / "bad.ttf", ui_bold_font=None))
    assert not output.exists()


def test_pipeline_credit_preserves_separate_noncommercial_observation_terms():
    renderer = importlib.import_module("render_web_demo")
    credit = renderer.pipeline_source_credit(
        {
            "creator": "Photographer",
            "observer": "Observer",
            "licence": "cc-by",
            "observation_licence": "cc-by-nc",
            "source_url": "https://example.test/public-source",
        }
    )
    assert credit["rights"]["photo_licence"] == "cc-by"
    assert credit["rights"]["observation_licence"] == "cc-by-nc"
    assert credit["rights"]["observer"] == "Observer"
    assert credit["rights"]["non_commercial"] is True


def test_website_frames_consume_private_pipeline_pixels(tmp_path):
    from PIL import Image

    captures = tmp_path / "captures"
    (captures / "review-snapshot").mkdir(parents=True)
    (captures / "review-snapshot/capture-provenance.json").write_text('{"photos": []}')
    original, checked = tmp_path / "original", tmp_path / "checked"
    original.mkdir()
    checked.mkdir()
    Image.new("RGB", (3, 3), "red").save(original / "original-ui.png")
    Image.new("RGB", (3, 3), "green").save(checked / "original-ui.png")
    frames = importlib.import_module("web_demo_frames").WebsiteFrames(
        captures, checked, Path("unused"), Path("unused")
    )
    canvas = Image.new("RGB", (3, 3))
    frames.evidence_photo(canvas, "original-ui.png", (0, 0, 3, 3))
    assert canvas.getpixel((0, 0)) == (0, 128, 0)


@pytest.mark.parametrize(
    "field,value", [("baseline", {"model": "other"}), ("selection", {"run_id": "other"})]
)
def test_same_hash_files_do_not_authorize_different_source_or_model(tmp_path, field, value):
    renderer = importlib.import_module("render_web_demo")
    proof = completed_pipeline(tmp_path)
    proof[field] = value
    (tmp_path / "capture-manifest.json").write_text(json.dumps(proof))
    with pytest.raises(ValueError, match="saved evidence"):
        renderer.validate_pipeline_capture(tmp_path)


@pytest.mark.parametrize(
    "override", ["/home/private/alternate-take.wav", r"C:\Users\private\alternate-take.wav"]
)
def test_published_v3_timeline_sanitizes_absolute_audio_overrides(tmp_path, monkeypatch, override):
    from argparse import Namespace

    renderer = importlib.import_module("render_web_demo")
    pipeline_dir = tmp_path / "pipeline"
    pipeline_dir.mkdir()
    proof = completed_pipeline(pipeline_dir)
    proof["description"] = "Technical serializer test fixture"
    scenes = [{"audio": "/home/private/resolved-take.wav", "audio_file": override}]
    monkeypatch.setattr(renderer, "load_timeline", lambda *_: scenes)
    monkeypatch.setattr(renderer, "caption_cues", lambda *_: [])
    monkeypatch.setattr(renderer, "narration_master", lambda *_: None)
    monkeypatch.setattr(renderer, "WebsiteFrames", lambda *_: None)
    monkeypatch.setattr(renderer, "encode_picture", lambda *_: None)
    transcript = tmp_path / "transcript.json"
    transcript.write_text('{"scenes": []}')
    font = tmp_path / "font.ttf"
    font.write_bytes(b"serializer-only fixture; no font rendering")
    args = Namespace(
        script=Path("unused"),
        audio=Path("unused"),
        transcript=transcript,
        credit_font=font,
        ffmpeg=Path("unused"),
    )
    output = tmp_path / "published"
    renderer._render(args, output, proof, pipeline_dir, Path("unused"), {"photos": []})
    published = json.loads((output / "timeline.json").read_text())
    assert published[0]["audio_file"] == "alternate-take.wav"
    assert published[0]["audio"] == "resolved-take.wav"
    assert scenes[0]["audio_file"] == override
