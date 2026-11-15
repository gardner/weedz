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
