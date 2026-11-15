"""Publication accepts only a pinned immutable machine-prediction package."""

import hashlib
import json

import pytest
from test_annotation_samples import canonical_batch as canonical_batch

from weedz.annotation.samples import export_samples
from weedz.batches.package import validate_package


def exported(canonical_batch, tmp_path):
    manifest, frame, _ = canonical_batch
    output = tmp_path / "export"
    export_samples(manifest, output, frame_results=frame)
    return output


def manifest_sha(output):
    return hashlib.sha256((output / "manifest.json").read_bytes()).hexdigest()


def test_verified_package_retains_canonical_image_and_task_identity(canonical_batch, tmp_path):
    output = exported(canonical_batch, tmp_path)
    package = validate_package(output, manifest_sha(output))
    assert len(package.tasks) == 1
    assert package.tasks[0]["meta"]["external_id"] == canonical_batch[2]
    assert len(package.images) == 1


def test_package_cannot_smuggle_human_annotations_even_with_updated_file_hash(
    canonical_batch, tmp_path
):
    output = exported(canonical_batch, tmp_path)
    tasks = json.loads((output / "tasks.json").read_text())
    tasks[0]["annotations"] = [{"result": []}]
    (output / "tasks.json").write_text(json.dumps(tasks))
    manifest = json.loads((output / "manifest.json").read_text())
    manifest["files"]["tasks.json"] = hashlib.sha256(
        (output / "tasks.json").read_bytes()
    ).hexdigest()
    (output / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="machine|annotations"):
        validate_package(output, manifest_sha(output))


def test_mutated_image_cannot_be_published_under_original_attribution(canonical_batch, tmp_path):
    output = exported(canonical_batch, tmp_path)
    image = next((output / "images").rglob("*.png"))
    image.write_bytes(b"changed")
    with pytest.raises(ValueError, match="checksum"):
        validate_package(output, manifest_sha(output))
