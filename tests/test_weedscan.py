import hashlib
import json
from types import SimpleNamespace

import numpy as np
import pytest
from PIL import Image

from weedz.classification import weedscan


def test_verified_snapshot_and_bounded_read(tmp_path, monkeypatch):
    path = tmp_path / "weights"
    path.write_bytes(b"weights")
    digest = hashlib.sha256(b"weights").hexdigest()
    assert weedscan.verified_bytes(path, digest) == b"weights"
    with pytest.raises(ValueError, match="checksum"):
        weedscan.verified_bytes(path, "0" * 64)
    monkeypatch.setattr(weedscan, "MAX_ARTIFACT_BYTES", 2)
    with pytest.raises(ValueError, match="cap"):
        weedscan.verified_bytes(path, digest)


def test_taxonomy_numeric_order_preserves_genus_and_subspecies():
    rows = [
        {"Embedding": 1, "ScientificName": "Cytisus scoparius subsp scoparius"},
        {"Embedding": 0, "ScientificName": "Cortaderia"},
    ]
    assert weedscan.class_labels(json.dumps(rows).encode(), 2) == (
        "Cortaderia",
        "Cytisus scoparius subsp scoparius",
    )
    for bad in (
        [rows[0], rows[0]],
        [{"Embedding": True, "ScientificName": "A"}],
        [{"Embedding": 0, "ScientificName": ""}],
    ):
        with pytest.raises(ValueError, match="mapping"):
            weedscan.class_labels(json.dumps(bad).encode(), len(bad))


def test_preprocess_bicubic_ties_even_and_no_exif_rotation():
    pixels = np.zeros((480, 639, 3), dtype=np.uint8)
    pixels[:, 80] = (255, 128, 0)
    image = Image.fromarray(pixels)
    image.getexif()[274] = 6
    result = weedscan.preprocess(image)
    assert result.shape == (1, 3, 480, 480)
    assert result.dtype == np.float32
    np.testing.assert_allclose(
        result[0, :, 0, 0],
        (np.array([255, 128, 0]) - [123.675, 116.28, 103.53]) / [58.395, 57.12, 57.375],
        atol=3e-7,
    )
    assert result.flags.c_contiguous


def test_extreme_aspect_refused_before_resize(monkeypatch):
    image = Image.new("RGB", (1, 100000))
    monkeypatch.setattr(Image.Image, "resize", lambda *a, **k: pytest.fail("allocated"))
    with pytest.raises(ValueError, match="pixel cap"):
        weedscan.preprocess(image)


def test_rank_keeps_released_probabilities_without_second_softmax():
    rows = weedscan.rank_scores(np.array([0.1, 0.45, 0.45]), ("Z", "B", "A"), 2)
    assert [(r["taxon"], r["score"]) for r in rows] == [("B", 0.45), ("A", 0.45)]
    assert rows[0]["score_kind"] == "closed_set_softmax_uncalibrated"


@pytest.mark.parametrize("scores", [[np.nan, 1], [np.inf, 0], [-0.1, 1.1], [0.2, 0.2], [1]])
def test_invalid_score_contract(scores):
    with pytest.raises(ValueError):
        weedscan.rank_scores(np.array(scores), ("A", "B"), 1)


def test_load_verified_bytes_contract_predict_callback(tmp_path, monkeypatch):
    checkpoint, labels = tmp_path / "model", tmp_path / "labels"
    checkpoint.write_bytes(b"model")
    labels.write_text(
        json.dumps(
            [
                {"Embedding": 0, "ScientificName": "Cortaderia"},
                {"Embedding": 1, "ScientificName": "Ulex europaeus"},
            ]
        )
    )
    monkeypatch.setattr(weedscan, "CLASS_COUNT", 2)
    monkeypatch.setattr(weedscan, "WEIGHTS_SHA256", hashlib.sha256(b"model").hexdigest())
    monkeypatch.setattr(weedscan, "LABELS_SHA256", hashlib.sha256(labels.read_bytes()).hexdigest())
    input_node = SimpleNamespace(
        name="input", shape=["batch_size", 3, "height", "width"], type="tensor(float)"
    )
    output_node = SimpleNamespace(name="output", shape=["batch_size", 2], type="tensor(float)")

    class Session:
        def get_inputs(self):
            return [input_node]

        def get_outputs(self):
            return [output_node]

        def get_providers(self):
            return ["CPUExecutionProvider"]

        def run(self, names, feeds):
            return [np.array([[0.2, 0.8]], dtype=np.float32)]

    def create(raw, **kwargs):
        assert raw == b"model"
        assert kwargs["providers"] == ["CPUExecutionProvider"]
        return Session()

    monkeypatch.setattr(
        weedscan.importlib,
        "import_module",
        lambda name: SimpleNamespace(SessionOptions=SimpleNamespace, InferenceSession=create),
    )
    model = weedscan.WeedScanClassifier.load(checkpoint, labels)
    captured = []
    model.on_scores = captured.append
    assert model.predict([Image.new("RGB", (480, 480))], top_k=2)[0][0]["taxon"] == "Ulex europaeus"
    assert captured[0].shape == (2,)
    assert model.metadata["pipeline_name"] == "WeedScan488"
    assert "torch" not in model.metadata
    output_node.type = "tensor(double)"
    with pytest.raises(ValueError, match="output"):
        weedscan.WeedScanClassifier.load(checkpoint, labels)
