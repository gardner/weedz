"""Only completed attributable human exports enter the offline import boundary."""

import pytest

from weedz.annotation.import_records import completed_records


def annotation():
    return {
        "id": 20,
        "task": 1,
        "completed_by": 7,
        "was_cancelled": False,
        "created_at": "2026-11-16T01:00:00Z",
        "updated_at": "2026-11-16T01:01:00Z",
        "result": [],
    }


def test_predictions_drafts_and_cancelled_work_are_never_imported():
    skipped = annotation() | {"id": 21, "was_cancelled": True}
    task = {
        "id": 1,
        "annotations": [annotation(), skipped],
        "predictions": [annotation()],
        "drafts": [annotation()],
    }
    rows = completed_records(task, "project-1")
    assert len(rows) == 1
    assert rows[0].actor == "label-studio:project-1:account:7"
    assert rows[0].revision == "label-studio:project-1:task:1:annotation:20:2026-11-16T01:01:00Z"


@pytest.mark.parametrize(
    "field,value",
    [
        ("completed_by", None),
        ("task", 2),
        ("updated_at", "bad"),
        ("was_cancelled", None),
        ("id", True),
    ],
)
def test_incomplete_or_mismatched_human_identity_fails(field, value):
    row = annotation() | {field: value}
    with pytest.raises(ValueError):
        completed_records({"id": 1, "annotations": [row]}, "project-1")
