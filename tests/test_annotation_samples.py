"""Canonical manifests export without inventing iNaturalist observation identities."""

import hashlib
import json
from pathlib import Path

import pytest
from PIL import Image

from weedz.annotation.samples import export_samples
from weedz.contract import Media, Rights, Sample
from weedz.manifest import write_manifest


@pytest.fixture
def canonical_batch(tmp_path: Path):
    root = tmp_path / "batch"
    (root / "images").mkdir(parents=True)
    image = root / "images/source.png"
    Image.new("RGB", (6, 4), "green").save(image)
    digest = hashlib.sha256(image.read_bytes()).hexdigest()
    sample = Sample(
        id="deepweeds:real-source.jpg",
        source="deepweeds",
        source_id="real-source.jpg",
        snapshot="pinned",
        rights=Rights(
            media_license="CC-BY-4.0",
            metadata_license="CC-BY-4.0",
            attribution="Olsen et al.",
            license_source="https://example.test/source",
        ),
        media=Media(uri=str(image), sha256=digest, width=6, height=4, format="PNG"),
        original_label="Private source class context",
        tasks=frozenset({"inference"}),
    )
    manifest = root / "samples.jsonl"
    manifest_sha = write_manifest(manifest, [sample])
    key = hashlib.sha256(f"{sample.id}:{digest}".encode()).hexdigest()
    frame = root / "frame.json"
    frame.write_text(
        json.dumps(
            {
                "model": {"revision": "pinned"},
                "manifest_sha256": manifest_sha,
                "predictions": [
                    {
                        "external_id": key,
                        "source_id": sample.id,
                        "image_sha256": digest,
                        "topk": [{"taxon": "Cotoneaster integerrimus Medik.", "score": 0.2}],
                    }
                ],
            }
        )
    )
    return manifest, frame, key


def test_canonical_source_identity_and_editable_frame_label(canonical_batch, tmp_path):
    manifest, frame, key = canonical_batch
    output = tmp_path / "export"
    export_samples(manifest, output, frame_results=frame)
    task = json.loads((output / "tasks.json").read_text())[0]
    assert task["meta"]["external_id"] == key
    assert task["data"]["source_dataset"] == "deepweeds"
    assert "Private source class" not in json.dumps(task)
    assert "observation_id" not in json.dumps(task) and "annotations" not in task
    text = next(r for r in task["predictions"][0]["result"] if r["from_name"] == "predicted_taxon")
    assert text["value"]["text"] == ["Cotoneaster integerrimus Medik."]
    assert not text.get("readonly", False)


def test_prediction_must_match_actual_model_input_media(canonical_batch, tmp_path):
    manifest, frame, _ = canonical_batch
    document = json.loads(frame.read_text())
    document["predictions"][0]["image_sha256"] = "0" * 64
    frame.write_text(json.dumps(document))
    output = tmp_path / "bad"
    with pytest.raises(ValueError, match="image.*checksum"):
        export_samples(manifest, output, frame_results=frame)
    assert not output.exists()
