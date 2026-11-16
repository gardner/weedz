"""New review evidence cannot change after its enclosing sample was validated."""

import json
from typing import Any, cast

import pytest

from weedz.contract import Completeness, ReviewEvent

SHA = "a" * 64


def test_evidence_is_copied_and_readonly():
    evidence = {"protocol": "pinned-source"}
    record = Completeness(
        id="c",
        task="detection",
        taxa=("Ulex",),
        status="exhaustive",
        origin="source",
        media_sha256=SHA,
        evidence=evidence,
    )
    evidence.clear()
    assert record.supervises()
    with pytest.raises((TypeError, AttributeError)):
        cast(Any, record.evidence).clear()
    assert json.loads(record.model_dump_json())["evidence"] == {"protocol": "pinned-source"}


def test_history_nested_objects_and_arrays_are_readonly_and_roundtrip_as_json():
    payload: dict[str, Any] = {"changes": [{"taxon": "Ulex"}], "geometry": [1, 2, 3, 4]}
    record = ReviewEvent(
        id="event",
        sample_id="s:1",
        media_sha256=SHA,
        origin="source",
        actor="publisher",
        action="published",
        dimension="annotation",
        payload=payload,
    )
    before = record.model_dump_json()
    payload["changes"][0]["taxon"] = "changed"
    assert record.model_dump_json() == before
    with pytest.raises((TypeError, AttributeError)):
        cast(Any, record.payload)["changes"][0]["taxon"] = "changed"
    with pytest.raises((TypeError, AttributeError)):
        cast(Any, record.payload)["changes"].append({})
    dumped = record.model_dump(mode="json")
    assert dumped["payload"] == {"changes": [{"taxon": "Ulex"}], "geometry": [1, 2, 3, 4]}
    assert ReviewEvent.model_validate(dumped).model_dump_json() == before


def test_default_review_mappings_are_readonly_too():
    record = ReviewEvent(
        id="event",
        sample_id="s:1",
        media_sha256=SHA,
        origin="source",
        actor="publisher",
        action="published",
        dimension="annotation",
    )
    with pytest.raises((TypeError, AttributeError)):
        cast(Any, record.payload)["new"] = "changed"


def test_readonly_json_does_not_coerce_non_json_bytes_into_review_claims():
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        ReviewEvent.model_validate(
            dict(
                id="event",
                sample_id="s:1",
                media_sha256=SHA,
                origin="source",
                actor="publisher",
                action="published",
                dimension="annotation",
                payload={"value": b"bytes"},
            )
        )
