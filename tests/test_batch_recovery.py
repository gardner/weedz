"""Failures between durable side effects and activity acknowledgement are resumable."""

import json

import pytest
from temporalio.testing import ActivityEnvironment
from test_batch_compute import Model
from test_batch_proposals import Proposer
from test_closed_batch import batch as batch
from test_closed_batch import reference

from weedz.batches.activities import BatchActivities, BatchRegistry
from weedz.batches.profiles import ModelProfile


def prepared(batch):
    root, manifest, ready, _ = batch
    sam, classifier = Proposer(), Model()
    registry = BatchRegistry(
        {"sam-v1": ModelProfile("sam-v1", "proposals", sam.metadata, lambda: sam)},
        {
            "classifier-v1": {
                "frame": ModelProfile("frame-v1", "frame", classifier.metadata, lambda: classifier)
            }
        },
    )
    activities = BatchActivities(root, registry)
    payload = {
        "request": {
            "manifest": reference(manifest, root),
            "ready": reference(ready, root),
            "segmentation_profile": "sam-v1",
            "classifier_profile": "classifier-v1",
            "variants": ["frame"],
            "project_id": 1,
        },
        "completed": {},
    }
    env = ActivityEnvironment()
    for method in (
        activities.batch_validate_v1,
        activities.batch_segment_v1,
        activities.batch_classify_frame_v1,
    ):
        payload["completed"][method.__name__] = env.run(method, payload)
    return root, activities, payload, env


def test_durable_publication_result_survives_missing_activity_receipt(batch, monkeypatch):
    import weedz.batches.activities as module

    root, activities, payload, env = prepared(batch)
    payload["completed"]["batch_package_v1"] = env.run(activities.batch_package_v1, payload)
    calls = []

    def publish(package, project):
        calls.append(1)
        return {
            "schema": 1,
            "project_id": project,
            "package_sha256": package.sha256,
            "tasks": 1,
            "new_tasks": 1 if len(calls) == 1 else 0,
            "new_predictions": 0,
            "human_annotation_writes": 0,
        }

    activities.publisher = publish
    original = module.write_receipt

    def interrupted(root, path, value):
        if path.endswith("batch_publish_v1.json"):
            raise OSError("Lost activity acknowledgement")
        return original(root, path, value)

    monkeypatch.setattr(module, "write_receipt", interrupted)
    with pytest.raises(OSError, match="acknowledgement"):
        env.run(activities.batch_publish_v1, payload)
    monkeypatch.setattr(module, "write_receipt", original)
    result = env.run(activities.batch_publish_v1, payload)
    assert len(calls) == 1
    receipt = json.loads((root / result["path"]).read_text())
    publication = json.loads((root / receipt["artifact"]["path"]).read_text())
    assert publication["new_tasks"] == 1


def test_replaced_inference_input_cannot_publish_a_package(batch, monkeypatch):
    import weedz.batches.package_build as module

    root, activities, payload, env = prepared(batch)
    receipt = json.loads(
        (root / payload["completed"]["batch_classify_frame_v1"]["path"]).read_text()
    )
    frame = root / receipt["artifact"]["path"]
    original = module.export_samples

    def replace_then_export(*args, **kwargs):
        document = json.loads(frame.read_text())
        document["predictions"][0]["topk"][0]["taxon"] = "Replaced prediction"
        frame.write_text(json.dumps(document))
        return original(*args, **kwargs)

    monkeypatch.setattr(module, "export_samples", replace_then_export)
    with pytest.raises(ValueError, match="checksum"):
        env.run(activities.batch_package_v1, payload)
    assert not (root / activities._context(payload).namespace / "package").exists()


def test_overlapping_publication_attempts_keep_identical_outer_receipts(batch):
    root, activities, payload, env = prepared(batch)
    payload["completed"]["batch_package_v1"] = env.run(activities.batch_package_v1, payload)
    calls = []

    def publish(package, project):
        calls.append(1)
        return {
            "schema": 1,
            "project_id": project,
            "package_sha256": package.sha256,
            "tasks": 1,
            "new_tasks": 1,
            "new_predictions": 0,
            "human_annotation_writes": 0,
        }

    activities.publisher = publish
    context = activities._context(payload)
    first = env.run(activities._publish, context)
    # A second attempt may have passed the outer receipt check before the first
    # attempt acknowledges it. Its durable side-effect result must be identical.
    overlap = env.run(activities._publish, context)
    assert overlap == first
    assert len(calls) == 1
