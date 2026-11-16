"""Gold promotion requires explicit, attributable accepted evidence and checked scope."""

from typing import Any

import pytest

from weedz.contract import Annotation, Completeness, ReviewEvent, Sample
from weedz.gold import ReviewPolicy, promote_detection

SHA = "a" * 64
WHEN = "2026-11-16T00:00:00Z"
TAXON = "Ulex europaeus"


def policy(**fields: Any) -> ReviewPolicy:
    return ReviewPolicy.model_validate(
        {
            "taxa": [TAXON],
            "min_reviewers": 1,
            "independent": True,
            "required_groups": ["site", "observer"],
            **fields,
        }
    )


def specimen(*, negative: bool = False) -> Sample:
    box = Annotation(
        id="review:box-1",
        supervision="box",
        taxon=TAXON,
        label="present",
        box=(1, 1, 10, 10),
        origin="reviewer",
        review="accepted",
        author="reviewer:author",
        reviewers=("reviewer:checker",),
        recorded_at=WHEN,
    )
    coverage = Completeness(
        id="review:coverage-1",
        media_sha256=SHA,
        task="detection",
        taxa=(TAXON,),
        status="exhaustive",
        origin="reviewer",
        author="reviewer:author",
        reviewers=("reviewer:checker",),
        review="accepted",
        recorded_at=WHEN,
        evidence={"export_sha256": SHA},
    )
    events = [
        ReviewEvent(
            id=f"review:event-{dimension}",
            sample_id="test:1",
            media_sha256=SHA,
            origin="reviewer",
            actor="reviewer:checker",
            recorded_at=WHEN,
            action="accepted",
            dimension=dimension,
            annotation_id=identifier,
            evidence={"export_sha256": SHA},
        )
        for dimension, identifier in [("completeness", coverage.id), ("identity", box.id)]
    ]
    return Sample.model_validate(
        {
            "id": "test:1",
            "source": "test",
            "source_id": "1",
            "snapshot": "v1",
            "rights": {
                "media_license": "cc-by-4.0",
                "metadata_license": "cc-by-4.0",
                "attribution": "Photographer",
                "license_source": "https://example.org",
            },
            "media": {"uri": "images/1.png", "sha256": SHA, "width": 40, "height": 30},
            "tasks": ["inference"],
            "annotations": [] if negative else [box],
            "completeness": [coverage],
            "review_history": events,
            "groups": {"site": "site:1", "observer": "observer:1"},
        }
    )


def changed(sample: Sample, **fields: Any) -> Sample:
    return Sample.model_validate(sample.model_dump(mode="json") | fields)


@pytest.mark.parametrize("negative", [False, True])
def test_accepted_boxes_and_checked_zero_box_negatives_are_promoted(negative: bool) -> None:
    source = specimen(negative=negative)
    promoted = promote_detection(source, policy())
    assert promoted.tasks == frozenset({"inference", "detection"})
    assert source.tasks == frozenset({"inference"})
    assert promoted.review_history == source.review_history
    assert promoted.annotations == source.annotations


@pytest.mark.parametrize("state", ["unreviewed", "uncertain", "rejected"])
def test_a_reviewer_box_is_not_gold_merely_because_someone_drew_it(state: str) -> None:
    sample = specimen()
    box = sample.annotations[0].model_dump(mode="json") | {"review": state}
    with pytest.raises(ValueError, match="accepted"):
        promote_detection(changed(sample, annotations=[box]), policy())


def test_upstream_source_labels_stay_usable_but_do_not_become_our_gold() -> None:
    sample = specimen()
    box = sample.annotations[0].model_dump(mode="json") | {
        "origin": "source",
        "review": "unreviewed",
    }
    source = changed(sample, annotations=[box])
    assert source.annotations[0].supervises()
    with pytest.raises(ValueError, match="accepted"):
        promote_detection(source, policy())


def test_a_list_of_reviewer_names_without_their_targeted_history_is_not_acceptance() -> None:
    sample = specimen()
    with pytest.raises(ValueError, match="history"):
        promote_detection(changed(sample, review_history=[]), policy())


def test_reopening_the_identity_vote_revokes_eligibility() -> None:
    sample = specimen()
    previous = sample.review_history[-1]
    reopened = ReviewEvent(
        id="review:reopened",
        sample_id=sample.id,
        media_sha256=SHA,
        origin="reviewer",
        actor=previous.actor,
        recorded_at=WHEN,
        action="reopened",
        dimension="identity",
        annotation_id="review:box-1",
        supersedes=previous.id,
        evidence={"export_sha256": SHA},
    )
    with pytest.raises(ValueError, match="history"):
        promote_detection(
            changed(sample, review_history=[*sample.review_history, reopened]), policy()
        )


def test_a_self_review_cannot_meet_an_independent_review_policy() -> None:
    sample = specimen()
    box = sample.annotations[0].model_dump(mode="json") | {"author": "reviewer:checker"}
    with pytest.raises(ValueError, match="independent|reviewer"):
        promote_detection(changed(sample, annotations=[box]), policy())


def test_review_counts_and_allowed_reviewer_ids_are_explicit() -> None:
    with pytest.raises(ValueError, match="reviewer"):
        promote_detection(specimen(), policy(min_reviewers=2))
    with pytest.raises(ValueError, match="reviewer"):
        promote_detection(specimen(), policy(reviewer_ids=["reviewer:other"]))


def test_completeness_must_cover_every_named_release_target() -> None:
    with pytest.raises(ValueError, match="scope"):
        promote_detection(specimen(), policy(taxa=[TAXON, "Clematis vitalba"]))


def test_a_documented_source_negative_is_not_an_accepted_human_gold_negative() -> None:
    sample = specimen(negative=True)
    coverage = sample.completeness[0].model_dump(mode="json") | {
        "origin": "source",
        "review": "unreviewed",
        "reviewers": [],
    }
    with pytest.raises(ValueError, match="completeness|accepted"):
        promote_detection(changed(sample, completeness=[coverage]), policy())


def test_missing_required_observer_or_site_evidence_is_not_a_fake_group() -> None:
    with pytest.raises(ValueError, match="observer"):
        promote_detection(changed(specimen(), groups={"site": "site:1"}), policy())


def test_model_suggestion_acceptance_does_not_supply_human_boxes() -> None:
    sample = specimen()
    predicted = sample.annotations[0].model_dump(mode="json") | {
        "origin": "model",
        "model": "sam+classifier",
        "author": None,
    }
    with pytest.raises(ValueError, match="completeness"):
        promote_detection(changed(sample, annotations=[predicted], completeness=[]), policy())


def test_a_reviewed_negative_can_retain_a_false_positive_model_suggestion() -> None:
    sample = specimen()
    predicted = sample.annotations[0].model_dump(mode="json") | {
        "origin": "model",
        "model": "sam+classifier",
        "author": None,
    }
    promoted = promote_detection(changed(sample, annotations=[predicted]), policy())
    assert promoted.annotations[0].origin == "model"
    assert not promoted.annotations[0].supervises()
