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


def test_revision_timestamp_cannot_precede_creation():
    row = annotation() | {"updated_at": "2026-11-15T01:00:00Z"}
    with pytest.raises(ValueError, match="timestamp"):
        completed_records({"id": 1, "annotations": [row]}, "project-1")


def test_actual_revision_actor_is_separate_from_original_annotation_author():
    row = annotation() | {"updated_by": {"id": 9}}
    record = completed_records({"id": 1, "annotations": [row]}, "project-1")[0]
    assert record.author == "label-studio:project-1:account:7"
    assert record.actor == "label-studio:project-1:account:9"
    assert record.actor_field == "updated_by"


def test_revision_digest_binds_both_actor_and_author_when_updated_by_is_present():
    row = annotation() | {"updated_by": 9}
    first = completed_records({"id": 1, "annotations": [row]}, "project-1")[0]
    changed = completed_records({"id": 1, "annotations": [row | {"completed_by": 8}]}, "project-1")[
        0
    ]
    assert first.revision == changed.revision and first.actor == changed.actor
    assert first.sha256 != changed.sha256
