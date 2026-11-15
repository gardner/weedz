import hashlib
import json

import numpy as np
import pytest
from PIL import Image

from weedz.classification.aotearoa import class_labels, preprocess, rank_logits, verified_bytes


def test_hash_mismatch_fails_before_loading_model(tmp_path):
    path = tmp_path / "model.onnx"
    path.write_bytes(b"changed")
    with pytest.raises(ValueError, match="checksum"):
        verified_bytes(path, "0" * 64)
    assert verified_bytes(path, hashlib.sha256(b"changed").hexdigest()) == b"changed"


def test_class_mapping_uses_numeric_output_order_not_json_insertion_order():
    data = {"1": {"scientific_name": "Animal species"}, "0": {"scientific_name": "Plant species"}}
    assert class_labels(json.dumps(data).encode(), expected_count=2) == (
        "Plant species",
        "Animal species",
    )
    for bad in ({"1": data["1"], "2": data["0"]}, {"0": data["0"], "1": data["0"]}):
        with pytest.raises(ValueError, match="mapping"):
            class_labels(json.dumps(bad).encode(), expected_count=2)


def test_preprocessing_preserves_aspect_then_center_crops_and_normalizes_rgb():
    image = Image.new("RGB", (832, 416), (255, 128, 0))
    pixels = np.asarray(image).copy()
    pixels[:, :208] = (0, 255, 0)
    tensor = preprocess(Image.fromarray(pixels))
    assert tensor.shape == (1, 3, 384, 384)
    assert tensor.dtype == np.float32
    np.testing.assert_allclose(tensor[0, :, 0, 0], [1, 128 / 127.5 - 1, -1], atol=1e-7)


def test_ranking_normalizes_against_all_classes_and_retains_nonplants():
    rows = rank_logits(np.array([0.0, 0.0, 0.0, 0.0]), ("Bird", "Fungus", "Gorse", "Other"), 2)
    assert [row["taxon"] for row in rows] == ["Bird", "Fungus"]
    assert [row["score"] for row in rows] == [0.25, 0.25]
    assert all(row["score_kind"] == "closed_set_softmax_uncalibrated" for row in rows)


@pytest.mark.parametrize(
    "logits", [np.array([np.nan, 1.0]), np.array([np.inf, 1.0]), np.array([1.0])]
)
def test_invalid_logits_are_refused(logits):
    with pytest.raises(ValueError):
        rank_logits(logits, ("A", "B"), 1)


def test_odd_center_crop_matches_released_extra_pixel_on_right():
    pixels = np.zeros((416, 417, 3), dtype=np.uint8)
    pixels[:, 16, :] = 255
    result = preprocess(Image.fromarray(pixels))
    assert result[0, 0, 0, 0] == 1
    assert result[0, 0, 0, 1] == -1


def test_nz_pipeline_identity_does_not_claim_plantclef_or_timm(tmp_path):
    from test_classification_batch import Classifier, corpus

    from weedz.classification.batch import classify_batch

    manifest, _ = corpus(tmp_path)
    model = Classifier()
    model.metadata = {
        "pipeline_name": "Aotearoa NZ",
        "frame_input_policy": "released416/384",
        "supported_profiles": ["frame"],
    }
    result = classify_batch(manifest, tmp_path, tmp_path / "nz.json", model)
    assert result["model_version"].startswith("Aotearoa NZ frame")
    assert result["model"]["input_policy"] == "released416/384"
    with pytest.raises(ValueError, match="profile"):
        classify_batch(manifest, tmp_path, tmp_path / "tiles.json", model, "tiles")


def test_session_uses_verified_bytes_and_refuses_changed_artifacts(tmp_path, monkeypatch):
    from weedz.classification import aotearoa

    checkpoint, mapping = tmp_path / "model", tmp_path / "labels"
    checkpoint.write_bytes(b"weights")
    mapping.write_text(json.dumps({"0": {"scientific_name": "Bird"}}), encoding="utf-8")
    monkeypatch.setattr(aotearoa, "WEIGHTS_SHA256", hashlib.sha256(b"weights").hexdigest())
    monkeypatch.setattr(aotearoa, "LABELS_SHA256", hashlib.sha256(mapping.read_bytes()).hexdigest())
    # Failure in mapping is reached before any ONNXRuntime import/session creation.
    monkeypatch.setattr(
        aotearoa.importlib, "import_module", lambda _: pytest.fail("loaded invalid mapping")
    )
    with pytest.raises(ValueError, match="mapping"):
        aotearoa.AotearoaClassifier.load(checkpoint, mapping)
    checkpoint.write_bytes(b"wrong")
    with pytest.raises(ValueError, match="checksum"):
        aotearoa.AotearoaClassifier.load(checkpoint, mapping)


def test_orientation_is_applied_before_resize_and_crop():
    image = Image.new("RGB", (416, 832), "red")
    pixels = np.asarray(image).copy()
    pixels[416:] = (0, 0, 255)
    image = Image.fromarray(pixels)
    image.getexif()[274] = 6
    tensor = preprocess(image)
    assert tensor[0, 2, 192, 0] == 1
    assert tensor[0, 0, 192, -1] == 1
