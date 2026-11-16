"""Direct human votes bind stable claim content, separately from aggregate vote state."""

import pytest
from test_gold_policy import changed, policy, specimen

from weedz.contract import ReviewEvent
from weedz.gold import promote_detection


@pytest.mark.parametrize("mutation", ["box", "taxon", "scope"])
def test_direct_acceptance_cannot_follow_changed_claim_content(mutation):
    sample = specimen()
    if mutation == "scope":
        coverage = sample.completeness[0].model_dump(mode="json")
        coverage["taxa"] = ["Ulex europaeus", "Cytisus scoparius"]
        sample = changed(sample, completeness=[coverage])
        selected = policy(taxa=coverage["taxa"])
    else:
        box = sample.annotations[0].model_dump(mode="json")
        box.update({"box": [2, 2, 20, 20]} if mutation == "box" else {"taxon": "Cytisus scoparius"})
        sample = changed(sample, annotations=[box])
        selected = policy()
    with pytest.raises(ValueError, match="history"):
        promote_detection(sample, selected)


def test_missing_snapshot_is_legacy_history_not_gold_acceptance():
    sample = specimen()
    history = [event.model_dump(mode="json") | {"payload": {}} for event in sample.review_history]
    with pytest.raises(ValueError, match="history"):
        promote_detection(changed(sample, review_history=history), policy())


@pytest.mark.parametrize("action", ["rejected", "reopened"])
@pytest.mark.parametrize("supersede", [False, True])
def test_same_claim_rejection_or_reopen_vetoes_even_with_different_vote_state(action, supersede):
    sample = specimen()
    prior = sample.review_history[-1]
    assert sample.media.sha256 is not None
    snapshot = sample.annotations[0].model_dump(mode="json") | {
        "review": "rejected" if action == "rejected" else "unreviewed",
        "reviewers": [],
    }
    vote = ReviewEvent(
        id="later-vote",
        sample_id=sample.id,
        media_sha256=sample.media.sha256,
        origin="reviewer",
        actor=prior.actor,
        recorded_at="2026-11-16T01:00:00Z",
        action=action,
        dimension="identity",
        annotation_id=sample.annotations[0].id,
        supersedes=prior.id if supersede else None,
        payload={"claim": snapshot},
    )
    with pytest.raises(ValueError, match="history"):
        promote_detection(changed(sample, review_history=[*sample.review_history, vote]), policy())
