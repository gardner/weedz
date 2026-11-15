import hashlib

import pytest
from PIL import Image
from test_contract import sample

from weedz.classification.batch import classify_batch
from weedz.contract import Sample
from weedz.manifest import write_manifest


class Classifier:
    metadata = {"model": "test classifier", "weights_sha256": "a" * 64}
    calls = 0

    def predict(self, images, top_k=5):
        self.calls += 1
        return [
            [
                {
                    "taxon": "Example species",
                    "score": 0.4,
                    "score_kind": "closed_set_softmax_uncalibrated",
                }
            ]
            for _ in images
        ]


def corpus(tmp_path):
    image = tmp_path / "image.png"
    Image.new("RGB", (32, 32), "green").save(image)
    sha = hashlib.sha256(image.read_bytes()).hexdigest()
    record = Sample.model_validate(
        sample(
            media={"uri": "image.png", "sha256": sha, "width": 32, "height": 32},
            tasks=["inference"],
            annotations=[],
        )
    )
    manifest = tmp_path / "samples.jsonl"
    write_manifest(manifest, [record])
    return manifest, image


def test_matching_completed_batch_resumes_without_new_model_calls(tmp_path):
    manifest, _ = corpus(tmp_path)
    model = Classifier()
    out = tmp_path / "predictions.json"
    first = classify_batch(manifest, tmp_path, out, model)
    second = classify_batch(manifest, tmp_path, out, model)
    assert first == second
    assert model.calls == 1
    assert first["predictions"][0]["source_id"] == "test:1"
    assert "annotations" not in first


def test_cache_never_hides_changed_source_pixels(tmp_path):
    manifest, image = corpus(tmp_path)
    model = Classifier()
    out = tmp_path / "predictions.json"
    classify_batch(manifest, tmp_path, out, model)
    image.write_bytes(b"changed pixels")
    with pytest.raises(ValueError, match="checksum"):
        classify_batch(manifest, tmp_path, out, model)
    assert model.calls == 1


def test_tiled_predictions_keep_regions_without_claiming_masks(tmp_path):
    manifest, _ = corpus(tmp_path)
    result = classify_batch(manifest, tmp_path, tmp_path / "tiles.json", Classifier(), "tiles")
    row = result["predictions"][0]
    assert len(row["views"]) > 1
    assert all("box" in view and "mask" not in view for view in row["views"])
    assert row["topk"][0]["score_kind"] == "maximum_closed_set_softmax_across_views_uncalibrated"
