"""Activity boundaries persist verified receipts and never repeat a completed model stage."""

import json
import os
import stat

from temporalio.testing import ActivityEnvironment
from test_batch_compute import Model
from test_batch_proposals import Proposer
from test_closed_batch import batch as batch
from test_closed_batch import reference

from weedz.batches.activities import BatchActivities, BatchRegistry
from weedz.batches.profiles import ModelProfile


def test_real_activity_boundaries_package_and_resume_without_reloading_models(batch, monkeypatch):
    root, manifest, ready, _ = batch
    sam, classifier = Proposer(), Model()
    registry = BatchRegistry(
        {"sam2-v1": ModelProfile("sam2-v1", "proposals", sam.metadata, lambda: sam)},
        {
            "plantclef-v1": {
                "frame": ModelProfile("frame-v1", "frame", classifier.metadata, lambda: classifier)
            }
        },
    )
    request = {
        "manifest": reference(manifest, root),
        "ready": reference(ready, root),
        "segmentation_profile": "sam2-v1",
        "classifier_profile": "plantclef-v1",
        "variants": ["frame"],
        "project_id": 1,
    }
    activities = BatchActivities(root, registry)
    payload = {"request": request, "completed": {}}
    synced = set()
    real_sync, real_rename = os.fsync, os.rename

    def sync(fd):
        info = os.fstat(fd)
        if stat.S_ISREG(info.st_mode):
            synced.add((info.st_dev, info.st_ino))
        return real_sync(fd)

    def rename(source, destination):
        required = {(p.stat().st_dev, p.stat().st_ino) for p in source.rglob("*") if p.is_file()}
        assert required <= synced, "Package files must be durable before final publication"
        return real_rename(source, destination)

    monkeypatch.setattr("weedz.batches.package_build.os.fsync", sync)
    monkeypatch.setattr("weedz.batches.package_build.os.rename", rename)
    environment = ActivityEnvironment()
    for method in [
        activities.batch_validate_v1,
        activities.batch_segment_v1,
        activities.batch_classify_frame_v1,
        activities.batch_package_v1,
    ]:
        result = environment.run(method, payload)
        payload["completed"][method.__name__] = result
    first = payload["completed"]["batch_segment_v1"]
    assert environment.run(activities.batch_segment_v1, payload) == first
    assert sam.calls == 1 and classifier.calls == 1
    receipt = json.loads((root / payload["completed"]["batch_package_v1"]["path"]).read_text())
    manifest = json.loads((root / receipt["artifact"]["path"]).read_text())
    assert manifest["task_count"] == 1


def test_cached_activity_reestablishes_failed_receipt_directory_barriers(batch, monkeypatch):
    import pytest

    import weedz.batches.receipts as receipts

    root, manifest, ready, _ = batch
    sam, classifier = Proposer(), Model()
    registry = BatchRegistry(
        {"sam2-v1": ModelProfile("sam2-v1", "proposals", sam.metadata, lambda: sam)},
        {
            "plantclef-v1": {
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
            "classifier_profile": "plantclef-v1",
            "variants": ["frame"],
            "project_id": 1,
        },
        "completed": {},
    }
    context = activities._context(payload)
    target = root / context.namespace / "batch_validate_v1.json"
    real, barriers = receipts._sync, []
    failed = False

    def sync(directory):
        nonlocal failed
        if directory == target.parent and target.exists() and not failed:
            failed = True
            raise OSError("Interrupted receipt publication sync")
        barriers.append(directory)
        return real(directory)

    monkeypatch.setattr(receipts, "_sync", sync)
    environment = ActivityEnvironment()
    with pytest.raises(OSError):
        environment.run(activities.batch_validate_v1, payload)
    assert target.is_file()
    barriers.clear()
    environment.run(activities.batch_validate_v1, payload)
    assert target.parent in barriers and root in barriers
