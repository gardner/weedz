"""Canonical batches route real compute stages and keep large artifacts out of history."""

import asyncio

import pytest

from weedz.batches.workflow import BatchAnnotationWorkflow


def request():
    return {
        "manifest": {"path": "batch-0001/samples.jsonl", "sha256": "a" * 64},
        "ready": {"path": "batch-0001/ready.json", "sha256": "b" * 64},
        "segmentation_profile": "sam2.1-tiny-v1",
        "classifier_profile": "plantclef-frame-tiles-regions-v1",
        "variants": ["frame", "tiles", "regions"],
        "project_id": 1,
    }


def test_batch_routes_compute_and_publication_without_large_history_payloads(monkeypatch):
    calls = []

    async def execute(name, payload, **options):
        calls.append((name, payload, options))
        return {"path": f"batch-0001/{name}.json", "sha256": "c" * 64}

    monkeypatch.setattr("weedz.batches.workflow.workflow.execute_activity", execute)
    result = asyncio.run(BatchAnnotationWorkflow().run(request()))
    assert [name for name, _, _ in calls] == [
        "batch_validate_v1",
        "batch_segment_v1",
        "batch_classify_frame_v1",
        "batch_classify_tiles_v1",
        "batch_classify_regions_v1",
        "batch_package_v1",
        "batch_publish_v1",
    ]
    assert [options["task_queue"] for _, _, options in calls] == [
        "weedz-batch-control-v1",
        "weedz-batch-segmentation-v1",
        "weedz-batch-classification-v1",
        "weedz-batch-classification-v1",
        "weedz-batch-classification-v1",
        "weedz-batch-control-v1",
        "weedz-batch-publication-v1",
    ]
    assert result == {"path": "batch-0001/batch_publish_v1.json", "sha256": "c" * 64}
    assert all("heartbeat_timeout" in options for _, _, options in calls)


@pytest.mark.parametrize(
    "change",
    [{"project_id": 0}, {"variants": ["frame", "frame"]}, {"segmentation_profile": "../untrusted"}],
)
def test_bad_requests_never_schedule_work(monkeypatch, change):
    async def execute(*_args, **_options):
        pytest.fail("Invalid batch must not schedule activities")

    monkeypatch.setattr("weedz.batches.workflow.workflow.execute_activity", execute)
    with pytest.raises(ValueError):
        asyncio.run(BatchAnnotationWorkflow().run({**request(), **change}))


def test_large_or_inline_activity_result_never_reaches_another_activity(monkeypatch):
    calls = []

    async def execute(name, *_args, **_options):
        calls.append(name)
        return {"mask_png": "x" * 100_000}

    monkeypatch.setattr("weedz.batches.workflow.workflow.execute_activity", execute)
    with pytest.raises(ValueError):
        asyncio.run(BatchAnnotationWorkflow().run(request()))
    assert calls == ["batch_validate_v1"]


@pytest.mark.parametrize("path", ["/absolute", "../escape", "a/../escape", "a//b", "a\\b"])
def test_artifact_paths_cannot_escape_owned_storage(monkeypatch, path):
    async def execute(*_args, **_options):
        pytest.fail("Invalid artifact path must not schedule activities")

    monkeypatch.setattr("weedz.batches.workflow.workflow.execute_activity", execute)
    value = request()
    value["manifest"]["path"] = path
    with pytest.raises(ValueError):
        asyncio.run(BatchAnnotationWorkflow().run(value))


def test_failed_inference_never_packages_or_publishes(monkeypatch):
    calls = []

    async def execute(name, *_args, **_options):
        calls.append(name)
        if name == "batch_segment_v1":
            raise RuntimeError("Pinned model unavailable")
        return {"path": "batch-0001/validated.json", "sha256": "c" * 64}

    monkeypatch.setattr("weedz.batches.workflow.workflow.execute_activity", execute)
    with pytest.raises(RuntimeError, match="Pinned model unavailable"):
        asyncio.run(BatchAnnotationWorkflow().run(request()))
    assert calls == ["batch_validate_v1", "batch_segment_v1"]
