import hashlib
import json

import numpy as np
import pytest
from PIL import Image

from weedz.segmentation.batch import propose_batch


class Proposer:
    metadata = {"checkpoint": "real-model-pin", "configuration": "tiny-v1"}

    def __init__(self):
        self.calls = 0

    def generate(self, image):
        self.calls += 1
        mask = np.ones((image.height, image.width), dtype=bool)
        return [{"segmentation": mask, "predicted_iou": 0.8, "stability_score": 0.9}]


def source(tmp_path):
    image = tmp_path / "image.png"
    Image.new("RGB", (64, 64), "green").save(image)
    sample = {
        "id": "test:plant",
        "source": "test",
        "source_id": "plant",
        "snapshot": "v1",
        "rights": {
            "media_license": "CC-BY-4.0",
            "metadata_license": "CC-BY-4.0",
            "attribution": "Source creator",
            "license_source": "https://example.org/source",
        },
        "media": {
            "uri": str(image),
            "sha256": hashlib.sha256(image.read_bytes()).hexdigest(),
            "width": 64,
            "height": 64,
            "format": "PNG",
        },
        "tasks": ["inference"],
        "annotations": [],
    }
    manifest = tmp_path / "samples.jsonl"
    manifest.write_text(json.dumps(sample) + "\n")
    return manifest, image


def test_real_geometry_closed_hashes_and_completed_retry(tmp_path):
    manifest, _ = source(tmp_path)
    proposer = Proposer()
    output = tmp_path / "output"
    first = propose_batch(manifest, tmp_path, output, proposer)
    second = propose_batch(manifest, tmp_path, output, proposer)
    assert proposer.calls == 1
    assert first == second == json.loads((output / "ready.json").read_text())
    assert first["manifest_sha256"] == hashlib.sha256(manifest.read_bytes()).hexdigest()
    assert (
        first["proposals_sha256"]
        == hashlib.sha256((output / "proposals.jsonl").read_bytes()).hexdigest()
    )
    row = json.loads((output / "proposals.jsonl").read_text())
    assert row["sample_id"] == "test:plant"
    assert row["source_sample"]["annotations"] == []
    assert row["segmentation"]["regions"][0]["box"] == [0, 0, 64, 64]


def test_changed_manifest_or_pixels_cannot_inherit_completion(tmp_path):
    manifest, image = source(tmp_path)
    proposer = Proposer()
    output = tmp_path / "output"
    propose_batch(manifest, tmp_path, output, proposer)
    image.write_bytes(b"replaced")
    with pytest.raises(ValueError, match="checksum"):
        propose_batch(manifest, tmp_path, output, proposer)
    assert proposer.calls == 1


def test_manifest_pin_and_symlink_escape_fail_before_output(tmp_path):
    manifest, image = source(tmp_path)
    with pytest.raises(ValueError, match="manifest"):
        propose_batch(
            manifest, tmp_path, tmp_path / "out", Proposer(), expected_manifest_sha256="0" * 64
        )
    outside = tmp_path.parent / (tmp_path.name + "-outside.png")
    outside.write_bytes(image.read_bytes())
    image.unlink()
    image.symlink_to(outside)
    with pytest.raises(ValueError, match="media root"):
        propose_batch(manifest, tmp_path, tmp_path / "out", Proposer())
    assert not (tmp_path / "out").exists()


def test_interrupted_batch_resumes_only_uncommitted_samples(tmp_path):
    manifest, _ = source(tmp_path)
    first = json.loads(manifest.read_text())
    second = {**first, "id": "test:second", "source_id": "second"}
    manifest.write_text(json.dumps(first) + "\n" + json.dumps(second) + "\n")

    class Interrupted(Proposer):
        def generate(self, image):
            if self.calls == 1:
                self.calls += 1
                raise KeyboardInterrupt
            return super().generate(image)

    proposer = Interrupted()
    output = tmp_path / "output"
    with pytest.raises(KeyboardInterrupt):
        propose_batch(manifest, tmp_path, output, proposer)
    assert not (output / "ready.json").exists()
    resumed = Proposer()
    summary = propose_batch(manifest, tmp_path, output, resumed)
    assert resumed.calls == 1 and summary["count"] == 2


def test_failed_photos_retry_and_changed_model_refuses_closed_namespace(tmp_path):
    manifest, _ = source(tmp_path)

    class Failed(Proposer):
        def generate(self, image):
            raise RuntimeError("Real processing interrupted")

    output = tmp_path / "output"
    failed = propose_batch(manifest, tmp_path, output, Failed())
    assert failed["counts"] == {"ok": 0, "empty": 0, "failed": 1}
    model = Proposer()
    completed = propose_batch(manifest, tmp_path, output, model)
    assert model.calls == 1 and completed["counts"]["ok"] == 1
    model.metadata = {"checkpoint": "different-pin"}
    with pytest.raises(ValueError, match="provenance"):
        propose_batch(manifest, tmp_path, output, model)
