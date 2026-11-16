"""Explicit ingress must survive source restoration and remain in model identities."""

import hashlib
import json

import pytest
from test_annotation_versions import metadata
from test_classification_batch import Classifier
from test_classification_regions import inputs

from weedz.annotation.semantic import shared_regional_version
from weedz.batches.profiles import ModelProfile
from weedz.classification.regions import classify_region_batch, regional_metadata


def test_large_source_can_restore_and_resume_under_its_explicit_budget(tmp_path):
    manifest, proposals, row = inputs(tmp_path)
    image = tmp_path / "image.png"
    image.write_bytes(image.read_bytes() + bytes(20_000_000))
    sample = json.loads(manifest.read_text())
    sample["media"]["sha256"] = hashlib.sha256(image.read_bytes()).hexdigest()
    manifest.write_text(json.dumps(sample) + "\n")
    row["image_sha256"] = sample["media"]["sha256"]
    proposals.write_text(json.dumps(row) + "\n")
    model = Classifier()
    with pytest.raises(ValueError, match="cap"):
        classify_region_batch(manifest, tmp_path, proposals, tmp_path / "default", model, "sam3")
    assert model.calls == 0
    result = classify_region_batch(
        manifest,
        tmp_path,
        proposals,
        tmp_path / "explicit",
        model,
        "sam3",
        max_source_bytes=160_000_000,
    )
    assert model.calls == 1
    assert result["model"]["source_ingress"]["max_source_bytes"] == 160_000_000
    assert (
        classify_region_batch(
            manifest,
            tmp_path,
            proposals,
            tmp_path / "explicit",
            model,
            "sam3",
            max_source_bytes=160_000_000,
        )
        == result
    )
    assert model.calls == 1


def test_declared_budget_is_part_of_shared_and_resident_profile_identity():
    classifier, proposer = metadata()
    model = Classifier()
    model.metadata = classifier
    legacy = regional_metadata(model, proposer, "sam2")
    large = regional_metadata(model, proposer, "sam2", max_source_bytes=160_000_000)
    assert "source_ingress" not in legacy
    assert shared_regional_version(legacy)["sha256"] != shared_regional_version(large)["sha256"]
    a = ModelProfile("baseline", "regions", legacy, lambda: None)
    b = ModelProfile("large", "regions", large, lambda: None)
    assert a.sha256 != b.sha256
    assert not a.matches(large)


def test_ingress_identity_survives_equivalent_metadata_nesting():
    classifier, proposer = metadata()
    model = Classifier()
    model.metadata = classifier
    flat = regional_metadata(model, proposer, "sam2", max_source_bytes=160_000_000)
    nested = {
        "classifier": classifier,
        "proposer": proposer,
        **{
            key: flat[key]
            for key in ("source_ingress", "crop_geometry_revision", "masked_view_policy")
        },
    }
    assert shared_regional_version(flat) == shared_regional_version(nested)
