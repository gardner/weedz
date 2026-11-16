"""Checked negatives, functional source labels and review history remain distinct."""

from typing import Any

import pytest
from pydantic import ValidationError

from weedz.contract import Annotation, Completeness, ReviewEvent, Sample

SHA = "a" * 64
WHEN = "2026-11-16T00:00:00Z"


def record(**fields: Any) -> Sample:
    return Sample.model_validate(
        {
            "id": "test:1",
            "source": "test",
            "source_id": "1",
            "snapshot": "v1",
            "rights": {
                "media_license": "cc-by-4.0",
                "metadata_license": "cc-by-4.0",
                "attribution": "Publisher",
                "license_source": "https://example.org/data",
            },
            "media": {"uri": "images/1.png", "sha256": SHA, "width": 40, "height": 30},
            "tasks": ["inference"],
        }
        | fields
    )


def complete(**fields: Any) -> Completeness:
    return Completeness.model_validate(
        {
            "id": "review:complete-1",
            "media_sha256": SHA,
            "task": "detection",
            "scope": "whole_image",
            "taxa": ["Ulex europaeus"],
            "status": "exhaustive",
            "origin": "reviewer",
            "author": "reviewer:a",
            "review": "accepted",
            "reviewers": ["reviewer:b"],
            "recorded_at": WHEN,
            "evidence": {"export_sha256": "b" * 64},
        }
        | fields
    )


def event(**fields: Any) -> ReviewEvent:
    return ReviewEvent.model_validate(
        {
            "id": "review:event-1",
            "sample_id": "test:1",
            "media_sha256": SHA,
            "origin": "reviewer",
            "actor": "reviewer:b",
            "recorded_at": WHEN,
            "action": "accepted",
            "dimension": "completeness",
            "evidence": {"export_sha256": "b" * 64},
            "payload": {"completeness_id": "review:complete-1"},
        }
        | fields
    )


def test_a_functional_source_category_is_not_a_fabricated_taxon() -> None:
    label = Annotation(
        id="source:weed",
        supervision="image_class",
        category="weed",
        label="present",
        origin="source",
    )
    sample = record(tasks=["image_classification"], annotations=[label])
    assert sample.annotations[0].taxon is None
    assert sample.annotations[0].category == "weed"
    assert sample.annotations[0].review == "unreviewed"


def test_accepted_whole_image_completeness_supports_a_zero_box_detection_sample() -> None:
    sample = record(tasks=["detection"], completeness=[complete()], review_history=[event()])
    assert sample.annotations == ()
    assert sample.completeness[0].taxa == ("Ulex europaeus",)
    assert sample.completeness[0].supervises()


@pytest.mark.parametrize(
    "changes",
    [
        {"status": "partial"},
        {"status": "unknown"},
        {"review": "unreviewed"},
        {"review": "uncertain"},
        {"review": "rejected"},
        {"reviewers": []},
    ],
)
def test_unchecked_or_partial_coverage_never_creates_a_negative(changes: dict) -> None:
    with pytest.raises(ValidationError, match="detection needs"):
        record(tasks=["detection"], completeness=[complete(**changes)])


def test_documented_source_coverage_remains_source_evidence_not_our_human_acceptance() -> None:
    coverage = complete(
        origin="source",
        review="unreviewed",
        reviewers=[],
        author="source:publisher",
        recorded_at=None,
        taxa=[],
        categories=["weed"],
        evidence={"source_uri": "https://example.org/annotation-protocol"},
    )
    sample = record(tasks=["detection"], completeness=[coverage])
    assert sample.completeness[0].review == "unreviewed"
    with pytest.raises(ValidationError, match="detection needs"):
        record(tasks=["detection"], completeness=[coverage.model_copy(update={"evidence": {}})])


@pytest.mark.parametrize(
    "changes",
    [
        {"taxa": [], "categories": []},
        {"taxa": ["Ulex europaeus", "Ulex europaeus"]},
        {"origin": "model"},
        {"scope": "selected_regions"},
        {"recorded_at": None},
        {"recorded_at": "2026-11-16"},
    ],
)
def test_completeness_requires_an_explicit_scope_and_attributed_human_timestamp(
    changes: dict,
) -> None:
    with pytest.raises(ValidationError):
        complete(**changes)


def test_completeness_cannot_be_reused_for_changed_media() -> None:
    with pytest.raises(ValidationError, match="media"):
        record(completeness=[complete(media_sha256="b" * 64)])


@pytest.mark.parametrize(
    "changes",
    [
        {"sample_id": "test:2"},
        {"media_sha256": "b" * 64},
        {"supersedes": "missing:event"},
    ],
)
def test_history_cannot_be_attached_to_another_sample_or_unknown_revision(changes: dict) -> None:
    with pytest.raises(ValidationError, match="history|media|revision"):
        record(review_history=[event(**changes)])


def test_history_revisions_are_retained_and_event_ids_are_unique() -> None:
    first = event()
    second = event(id="review:event-2", action="reopened", supersedes=first.id)
    sample = record(review_history=[first, second])
    assert len(sample.review_history) == 2
    with pytest.raises(ValidationError, match="history"):
        record(review_history=[first, first])


def test_history_payloads_are_json_finite() -> None:
    with pytest.raises(ValidationError):
        event(payload={"nested": {"score": float("nan")}})


def test_new_mask_hashes_do_not_turn_masks_into_boxes() -> None:
    mask = Annotation(
        id="source:mask",
        supervision="dense_mask",
        category="weed",
        label="present",
        origin="source",
        mask_uri="masks/1.png",
        mask_sha256=SHA,
    )
    assert record(tasks=["segmentation"], annotations=[mask])
    with pytest.raises(ValidationError, match="detection needs"):
        record(tasks=["detection"], annotations=[mask])
    with pytest.raises(ValidationError, match="mask"):
        Annotation(
            id="source:box",
            supervision="box",
            taxon="Ulex europaeus",
            label="present",
            origin="source",
            box=(1, 1, 2, 2),
            mask_sha256=SHA,
        )


@pytest.mark.parametrize(
    "kind,geometry",
    [
        ("image_class", {}),
        ("dense_mask", {"mask_uri": "masks/1.png", "mask_sha256": SHA}),
    ],
)
def test_detection_completeness_cannot_call_a_known_unboxed_positive_a_negative(
    kind: str, geometry: dict[str, Any]
) -> None:
    positive = Annotation.model_validate(
        {
            "id": "source:positive",
            "supervision": kind,
            "taxon": "Ulex europaeus",
            "label": "present",
            "origin": "source",
            **geometry,
        }
    )
    with pytest.raises(ValidationError, match="Completeness.*geometry"):
        record(tasks=["detection"], annotations=[positive], completeness=[complete()])


def test_scoped_completeness_does_not_require_geometry_for_other_taxa() -> None:
    other = Annotation(
        id="source:other",
        supervision="image_class",
        taxon="Other species",
        label="present",
        origin="source",
    )
    assert record(tasks=["detection"], annotations=[other], completeness=[complete()])


def test_a_real_box_can_coexist_with_its_mask_and_exhaustive_detection_review() -> None:
    box = Annotation(
        id="source:box",
        supervision="box",
        taxon="Ulex europaeus",
        label="present",
        origin="source",
        box=(1, 1, 4, 4),
    )
    mask = Annotation(
        id="source:mask",
        supervision="dense_mask",
        taxon="Ulex europaeus",
        label="present",
        origin="source",
        mask_uri="masks/1.png",
        mask_sha256=SHA,
    )
    assert record(tasks=["detection"], annotations=[box, mask], completeness=[complete()])


def test_absent_extensions_preserve_legacy_serialization() -> None:
    sample = record()
    encoded = sample.model_dump_json()
    for absent in ("completeness", "review_history", "category", "mask_sha256"):
        assert f'"{absent}"' not in encoded
    point = Annotation(
        id="survey",
        supervision="surveyed_point",
        taxon="Euphorbia esula",
        label="present",
        origin="source",
        point=(1, 1),
    )
    assert point.supervises() and point.review == "unreviewed"
