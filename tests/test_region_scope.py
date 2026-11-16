"""A missing label cannot silently become a task-specific negative."""

from typing import Any

from weedz.contract import Sample
from weedz.region_evaluation.scope import Target, assess_scope


def sample(**fields: Any) -> Sample:
    return Sample.model_validate(
        {
            "id": "cwfid:1",
            "source": "cwfid",
            "source_id": "1",
            "snapshot": "v1",
            "rights": {
                "media_license": "research",
                "metadata_license": "research",
                "attribution": "Publisher",
                "license_source": "https://example.org",
            },
            "media": {"uri": "1.png", "sha256": "a" * 64, "width": 10, "height": 10},
            "tasks": ["inference"],
        }
        | fields
    )


def coverage(**fields: Any) -> dict:
    return {
        "id": "coverage:1",
        "media_sha256": "a" * 64,
        "task": "detection",
        "categories": ["weed"],
        "status": "exhaustive",
        "origin": "source",
        "evidence": {"protocol_sha256": "b" * 64},
    } | fields


def test_empty_annotations_without_completeness_are_unassessed() -> None:
    result = assess_scope(sample(), task="detection", target=Target("category", "weed", "cwfid"))
    assert not result.exhaustive
    assert result.completeness_ids == ()


def test_documented_source_exhaustiveness_is_not_fake_gold_review() -> None:
    result = assess_scope(
        sample(completeness=[coverage()]),
        task="detection",
        target=Target("category", "weed", "cwfid"),
    )
    assert result.exhaustive
    assert result.completeness_ids == ("coverage:1",)
    assert result.origins == ("source",)


def test_source_category_scope_does_not_transfer_to_other_dataset_or_task() -> None:
    record = sample(completeness=[coverage()])
    assert not assess_scope(
        record, task="segmentation", target=Target("category", "weed", "cwfid")
    ).exhaustive
    assert not assess_scope(
        record, task="detection", target=Target("category", "weed", "other")
    ).exhaustive
    assert not assess_scope(record, task="detection", target=Target("taxon", "weed")).exhaustive


def test_partial_and_rejected_coverage_do_not_establish_negatives() -> None:
    for fields in ({"status": "partial"}, {"review": "rejected"}, {"evidence": {}}):
        result = assess_scope(
            sample(completeness=[coverage(**fields)]),
            task="detection",
            target=Target("category", "weed", "cwfid"),
        )
        assert not result.exhaustive
