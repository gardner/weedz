"""Versioned commands preserve historical orchestration while adding real stage boundaries."""

import asyncio
from types import SimpleNamespace

import pytest

from weedz.discovery.workflows import DiscoveryWorkflow


@pytest.mark.parametrize(
    "profile,patched,expected",
    [
        ("off", True, ["collect_photos", "screen_photos", "export_run"]),
        (
            "sam2.1-tiny-v1",
            True,
            [
                "collect_photos",
                "segment_photos_v1",
                "screen_photos",
                "score_region_views_v1",
                "export_run",
            ],
        ),
        ("sam2.1-tiny-v1", False, ["collect_photos", "screen_photos", "export_run"]),
    ],
)
def test_versioned_stage_order_and_legacy_patch_branch(monkeypatch, profile, patched, expected):
    calls = []
    monkeypatch.setattr(
        "weedz.discovery.workflows.workflow.info", lambda: SimpleNamespace(workflow_id="run")
    )
    monkeypatch.setattr("weedz.discovery.workflows.workflow.patched", lambda _name: patched)

    async def execute(name, payload, **_options):
        calls.append(name)
        assert payload["run_id"] == "run"
        return {"schema": 1, "count": 2}

    monkeypatch.setattr("weedz.discovery.workflows.workflow.execute_activity", execute)
    asyncio.run(DiscoveryWorkflow().run({"segmentation": profile}))
    assert calls == expected


def test_segmented_completion_carries_partial_pipeline_outcome(monkeypatch):
    monkeypatch.setattr(
        "weedz.discovery.workflows.workflow.info", lambda: SimpleNamespace(workflow_id="run")
    )
    monkeypatch.setattr("weedz.discovery.workflows.workflow.patched", lambda _name: True)

    async def execute(name, _payload, **_options):
        return {"pipeline_outcome": "partial"} if name == "export_run" else {}

    monkeypatch.setattr("weedz.discovery.workflows.workflow.execute_activity", execute)
    result = asyncio.run(DiscoveryWorkflow().run({"segmentation": "sam2.1-tiny-v1"}))
    assert result["pipeline_outcome"] == "partial"
