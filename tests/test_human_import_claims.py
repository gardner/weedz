"""Readonly model evidence cannot silently become a human taxon annotation."""

import pytest

from weedz.annotation.import_claims import parse_claims
from weedz.annotation.import_records import completed_records


def record(extra):
    controls = [
        {"type": "choices", "from_name": name, "to_name": "image", "value": {"choices": values}}
        for name, values in (
            ("completeness_task", ["detection"]),
            ("review_status", ["accepted"]),
            ("completeness_status", ["exhaustive"]),
            ("completeness_taxa", ["Ulex europaeus"]),
        )
    ]
    return completed_records(
        {
            "id": 1,
            "annotations": [
                {
                    "id": 2,
                    "task": 1,
                    "was_cancelled": False,
                    "completed_by": 3,
                    "created_at": "2026-11-16T01:00:00Z",
                    "updated_at": "2026-11-16T01:01:00Z",
                    "result": controls + extra,
                }
            ],
        },
        "fixture",
    )[0]


def test_model_text_is_never_a_human_region():
    model = {
        "type": "textarea",
        "from_name": "model_evidence",
        "to_name": "image",
        "value": {"text": ["very confident gorse everywhere"]},
    }
    parsed = parse_claims(record([model]), (10, 10), {"Ulex europaeus"}, set())
    assert parsed.regions == ()
    assert parsed.decision.status == "exhaustive"


def test_unknown_annotation_controls_are_not_silently_discarded():
    with pytest.raises(ValueError, match="Unsupported"):
        parse_claims(record([{"type": "polygonlabels"}]), (10, 10), {"Ulex europaeus"}, set())
