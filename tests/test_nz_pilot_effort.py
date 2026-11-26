"""Pilot effort joins only verified tasks and records actual human submissions."""

import hashlib
import json
from pathlib import Path

import pytest

from weedz.annotation.pilot_effort import _package, summarize


def task(identifier: str) -> dict:
    return {
        "meta": {"external_id": identifier, "image_sha256": "a" * 64},
        "data": {"image": f"/data/{identifier}.png"},
    }


def answer(annotation_id: int, seconds: float | None, choice: str = "Unsure") -> dict:
    return {
        "id": annotation_id,
        "task": 7,
        "completed_by": 12,
        "was_cancelled": False,
        "lead_time": seconds,
        "result": [
            {
                "from_name": "watchlist_presence",
                "to_name": "image",
                "type": "choices",
                "value": {"choices": [choice]},
            }
        ],
    }


def test_counts_unreviewed_tasks_and_distinguishes_missing_times() -> None:
    first = task("one")
    exported = first | {"id": 7, "annotations": [answer(1, 12), answer(2, None)]}
    result = summarize([first, task("two")], [exported])
    assert result["planned_tasks"] == 2
    assert result["tasks_with_submission"] == 1
    assert result["submissions"] == 2
    assert result["watchlist_answers"] == {"Unsure": 2}
    assert result["timed_submissions"] == 1
    assert result["total_seconds"] == 12
    assert result["median_seconds"] == 12


def test_cancelled_seeded_and_draft_rows_are_not_timed() -> None:
    first = task("one")
    rows = [
        answer(1, 2) | {"was_cancelled": True},
        answer(2, 4) | {"ground_truth": True},
        answer(3, 8, "Watchlist plant visible"),
    ]
    exported = first | {"id": 7, "annotations": rows, "drafts": [answer(4, 16)]}
    result = summarize([first], [exported])
    assert result["submissions"] == 1
    assert result["cancelled_annotations"] == 1
    assert result["ground_truth_annotations"] == 1
    assert result["total_seconds"] == 8


def test_rejects_an_export_from_a_different_task_package() -> None:
    first = task("one")
    with pytest.raises(ValueError, match="match the package"):
        summarize([first], [task("two") | {"id": 7, "annotations": []}])
    with pytest.raises(ValueError, match="match the package"):
        summarize([first], [first | {"id": 7, "data": {}, "annotations": []}])


def test_duplicate_annotation_and_invalid_timing_are_rejected() -> None:
    first = task("one")
    with pytest.raises(ValueError, match="Duplicate annotation"):
        summarize([first], [first | {"id": 7, "annotations": [answer(1, 2), answer(1, 2)]}])
    with pytest.raises(ValueError, match="Invalid lead time"):
        summarize([first], [first | {"id": 7, "annotations": [answer(1, float("nan"))]}])


def test_package_rejects_a_manifest_for_the_other_arm(tmp_path: Path) -> None:
    raw = json.dumps([task("one")]).encode()
    (tmp_path / "tasks.json").write_bytes(raw)
    manifest = {
        "mode": "blind",
        "task_count": 1,
        "files": {"tasks.json": hashlib.sha256(raw).hexdigest()},
    }
    (tmp_path / "manifest.json").write_text(json.dumps(manifest))
    assert len(_package(tmp_path, "blind")[0]) == 1
    with pytest.raises(ValueError, match="assisted pilot package"):
        _package(tmp_path, "assisted")
