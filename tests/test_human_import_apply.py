"""Human revisions are attributable and idempotent; old decisions remain history."""

import pytest

from weedz.annotation.import_apply import apply_claims
from weedz.annotation.import_claims import parse_claims
from weedz.annotation.import_records import completed_records
from weedz.contract import Sample


def sample():
    return Sample.model_validate(
        dict(
            id="fixture:one",
            source="fixture",
            source_id="one",
            snapshot="v1",
            rights=dict(
                media_license="cc-by",
                metadata_license="cc-by",
                attribution="Fixture",
                license_source="https://example.org",
            ),
            media=dict(uri="images/a.png", sha256="a" * 64, width=100, height=100),
            tasks=["inference"],
        )
    )


def claims(time="2026-11-16T01:00:00Z", status="accepted"):
    results = [
        dict(type="choices", from_name=name, to_name="image", value={"choices": values})
        for name, values in (
            ("completeness_task", ["detection"]),
            ("review_status", [status]),
            ("completeness_status", ["exhaustive"]),
            ("completeness_taxa", ["Ulex europaeus"]),
        )
    ]
    record = completed_records(
        {
            "id": 1,
            "annotations": [
                dict(
                    id=2,
                    task=1,
                    completed_by=3,
                    was_cancelled=False,
                    created_at="2026-11-16T01:00:00Z",
                    updated_at=time,
                    result=results,
                )
            ],
        },
        "fixture",
    )[0]
    return parse_claims(record, (100, 100), {"Ulex europaeus"}, set())


def test_explicit_reviewed_negative_is_scoped_without_fictional_box():
    updated, masks = apply_claims(sample(), claims(), {"export_sha256": "b" * 64}, set())
    assert updated.annotations == () and masks == {}
    assert updated.completeness[0].taxa == ("Ulex europaeus",)
    assert updated.completeness[0].review == "accepted"
    assert updated.completeness[0].reviewers == ("label-studio:fixture:account:3",)
    assert len(updated.review_history) == 1
    repeated, _ = apply_claims(updated, claims(), {"export_sha256": "c" * 64}, set())
    assert repeated.model_dump_json() == updated.model_dump_json()


def test_changed_revision_replaces_standing_claim_and_preserves_history():
    first, _ = apply_claims(sample(), claims(), {}, set())
    revised, _ = apply_claims(first, claims("2026-11-16T02:00:00Z", "uncertain"), {}, set())
    assert revised.completeness[0].review == "uncertain"
    assert len(revised.review_history) == 2
    assert revised.review_history[1].supersedes == revised.review_history[0].id
    with pytest.raises(ValueError, match="revision"):
        apply_claims(first, claims(status="rejected"), {}, set())
