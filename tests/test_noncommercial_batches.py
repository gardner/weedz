"""Noncommercial handoffs need an explicit scope pinned through every publication step."""

import hashlib
import json

import pytest
from test_annotation_samples import canonical_batch as canonical_batch
from test_closed_batch import batch as batch
from test_closed_batch import reference

from weedz.annotation.samples import export_samples
from weedz.batches.contract import batch_request
from weedz.batches.package import validate_package
from weedz.batches.storage import validate_closed_batch
from weedz.rights_profiles import NONCOMMERCIAL_PROFILE, PUBLIC_PROFILE


@pytest.mark.parametrize("field", ["media_license", "metadata_license"])
def test_nc_media_and_metadata_require_explicit_export_and_publication_profiles(
    canonical_batch, tmp_path, field
):
    manifest, _frame, _key = canonical_batch
    value = json.loads(manifest.read_text())
    value["rights"][field] = "cc-by-nc-4.0"
    manifest.write_text(json.dumps(value) + "\n")
    output = tmp_path / "noncommercial"
    with pytest.raises(ValueError, match="licence"):
        export_samples(manifest, output)
    receipt = export_samples(manifest, output, rights_profile=NONCOMMERCIAL_PROFILE)
    assert receipt["rights_profile"] == NONCOMMERCIAL_PROFILE
    sha = hashlib.sha256((output / "manifest.json").read_bytes()).hexdigest()
    with pytest.raises(ValueError, match="profile"):
        validate_package(output, sha)
    package = validate_package(output, sha, rights_profile=NONCOMMERCIAL_PROFILE)
    assert package.rights_profile == NONCOMMERCIAL_PROFILE
    task = package.tasks[0]
    assert "CC BY-NC 4.0" in task["data"]["photo_credit"]
    assert "https://creativecommons.org/licenses/by-nc/4.0/" in task["data"]["photo_credit"]
    source = json.loads((output / "private/provenance.json").read_text())
    assert source["rights_profile"] == NONCOMMERCIAL_PROFILE
    assert source["samples"][0]["sample"]["rights"] == value["rights"]


def test_readiness_cannot_silently_change_an_existing_batch_purpose(batch):
    root, manifest, ready, _image = batch
    value = json.loads(manifest.read_text())
    value["rights"]["media_license"] = "cc-by-nc"
    manifest.write_text(json.dumps(value) + "\n")
    state = json.loads(ready.read_text())
    state["samples_sha256"] = reference(manifest, root)["sha256"]
    ready.write_text(json.dumps(state))
    with pytest.raises(ValueError, match="profile"):
        validate_closed_batch(
            root,
            reference(manifest, root),
            reference(ready, root),
            rights_profile=NONCOMMERCIAL_PROFILE,
        )
    state["rights_profile"] = NONCOMMERCIAL_PROFILE
    ready.write_text(json.dumps(state))
    with pytest.raises(ValueError, match="profile"):
        validate_closed_batch(root, reference(manifest, root), reference(ready, root))
    closed = validate_closed_batch(
        root,
        reference(manifest, root),
        reference(ready, root),
        rights_profile=NONCOMMERCIAL_PROFILE,
    )
    assert closed.rights_profile == NONCOMMERCIAL_PROFILE


def test_legacy_public_package_bytes_do_not_gain_optional_profile_fields(canonical_batch, tmp_path):
    manifest, _frame, _key = canonical_batch
    first, second = tmp_path / "default", tmp_path / "explicit-public"
    export_samples(manifest, first)
    export_samples(manifest, second, rights_profile=PUBLIC_PROFILE)
    files = {
        path.relative_to(first): path.read_bytes() for path in first.rglob("*") if path.is_file()
    }
    assert all((second / path).read_bytes() == raw for path, raw in files.items())
    assert "rights_profile" not in json.loads((first / "manifest.json").read_text())


def test_batch_request_preserves_explicit_purpose_and_refuses_unknown_profiles():
    request = {
        "manifest": {"path": "input.jsonl", "sha256": "a" * 64},
        "ready": {"path": "ready.json", "sha256": "b" * 64},
        "segmentation_profile": "sam2-v1",
        "classifier_profile": "plant-v1",
        "variants": ["regions"],
        "project_id": 1,
    }
    assert "rights_profile" not in batch_request(request)
    assert (
        batch_request(request | {"rights_profile": NONCOMMERCIAL_PROFILE})["rights_profile"]
        == NONCOMMERCIAL_PROFILE
    )
    with pytest.raises(ValueError, match="profile"):
        batch_request(request | {"rights_profile": "anything-goes"})


def test_noncommercial_activity_retry_keeps_its_purpose_without_repeating_models(batch):
    from temporalio.testing import ActivityEnvironment
    from test_batch_compute import Model
    from test_batch_proposals import Proposer

    from weedz.batches.activities import BatchActivities, BatchRegistry
    from weedz.batches.profiles import ModelProfile

    root, manifest, ready, _image = batch
    value = json.loads(manifest.read_text())
    value["rights"].update(media_license="cc-by-nc", metadata_license="cc-by-nc")
    manifest.write_text(json.dumps(value) + "\n")
    state = json.loads(ready.read_text())
    state.update(
        samples_sha256=reference(manifest, root)["sha256"], rights_profile=NONCOMMERCIAL_PROFILE
    )
    ready.write_text(json.dumps(state))
    sam, classifier = Proposer(), Model()
    registry = BatchRegistry(
        {"sam2-v1": ModelProfile("sam2-v1", "proposals", sam.metadata, lambda: sam)},
        {
            "plant-v1": {
                "frame": ModelProfile("frame-v1", "frame", classifier.metadata, lambda: classifier)
            }
        },
    )
    activities = BatchActivities(root, registry)
    payload = {
        "request": {
            "manifest": reference(manifest, root),
            "ready": reference(ready, root),
            "segmentation_profile": "sam2-v1",
            "classifier_profile": "plant-v1",
            "variants": ["frame"],
            "project_id": 1,
            "rights_profile": NONCOMMERCIAL_PROFILE,
        },
        "completed": {},
    }
    environment = ActivityEnvironment()
    for method in (
        activities.batch_validate_v1,
        activities.batch_segment_v1,
        activities.batch_classify_frame_v1,
        activities.batch_package_v1,
    ):
        result = environment.run(method, payload)
        payload["completed"][method.__name__] = result
    assert environment.run(activities.batch_package_v1, payload) == result
    assert sam.calls == classifier.calls == 1
    record = json.loads((root / result["path"]).read_text())
    package = validate_package(
        (root / record["artifact"]["path"]).parent,
        record["artifact"]["sha256"],
        rights_profile=NONCOMMERCIAL_PROFILE,
    )
    assert package.rights_profile == NONCOMMERCIAL_PROFILE
