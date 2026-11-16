"""An explicit accepted-review policy, separate from general upstream supervision.

Gold means the recorded policy passed, not that software established a reviewer's
botanical expertise. Reviewer identities/counts/independence and grouping are explicit.
"""

from collections.abc import Mapping

from pydantic import Field, field_validator, model_validator

from weedz.contract import Annotation, Completeness, Contract, ReviewEvent, Sample, Text
from weedz.review_values import thaw_json


class ReviewPolicy(Contract):
    taxa: tuple[Text, ...] = ()
    categories: tuple[Text, ...] = ()
    min_reviewers: int = Field(ge=1)
    independent: bool
    required_groups: tuple[Text, ...] = Field(min_length=1)
    reviewer_ids: tuple[Text, ...] = ()

    @field_validator("taxa", "categories", "required_groups", "reviewer_ids")
    @classmethod
    def unique_names(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if len(value) != len(set(value)):
            raise ValueError("Review policy cannot repeat a target, group or reviewer")
        return tuple(sorted(value))

    @model_validator(mode="after")
    def named_scope(self) -> "ReviewPolicy":
        if not self.taxa and not self.categories:
            raise ValueError("A gold review policy needs an explicit target scope")
        return self


Claim = Annotation | Completeness
STATES = {
    "accepted": "accepted",
    "confirmed": "accepted",
    "rejected": "rejected",
    "disputed": "rejected",
    "uncertain": "uncertain",
    "unresolved": "uncertain",
    "reopened": "unreviewed",
    "unreviewed": "unreviewed",
}


def _active_events(sample: Sample) -> list[ReviewEvent]:
    active: dict[str, ReviewEvent] = {}
    for event in sample.review_history:
        if event.supersedes:
            active.pop(event.supersedes, None)
        active[event.id] = event
    return list(active.values())


def _revision_state(event: ReviewEvent, claim: Claim) -> str | None:
    """Read only the supported claim snapshots, never the model evidence textarea."""
    if isinstance(claim, Completeness):
        data = event.payload.get("completeness")
        rows = (data,) if isinstance(data, Mapping) else ()
    else:
        data = event.payload.get("annotations")
        rows = data if isinstance(data, tuple) else ()
    for row in rows:
        if isinstance(row, Mapping) and row.get("id") == claim.id:
            if thaw_json(row) != claim.model_dump(mode="json"):
                return None
            state = row.get("review")
            return state if isinstance(state, str) else None
    return None


def _same_targeted_claim(event: ReviewEvent, claim: Claim) -> bool:
    snapshot = event.payload.get("claim")
    if not isinstance(snapshot, Mapping):
        return False
    # Vote state may change during rejection/reopening without changing the claim
    # being judged. All identity, geometry, authorship and derivation stay bound.
    ignored = {"review", "reviewers"}
    recorded = {key: thaw_json(value) for key, value in snapshot.items() if key not in ignored}
    expected = claim.model_dump(mode="json", exclude=ignored)
    return recorded == expected


def _event_state(event: ReviewEvent, claim: Claim) -> str | None:
    dimension = "completeness" if isinstance(claim, Completeness) else "identity"
    if (
        event.annotation_id == claim.id
        and event.dimension == dimension
        and _same_targeted_claim(event, claim)
    ):
        return STATES.get(event.action)
    if event.action == "completed_human_revision" and event.dimension == "annotation":
        return _revision_state(event, claim)
    return None


def _accepted_actors(sample: Sample, claim: Claim) -> set[str]:
    states: dict[str, set[str]] = {}
    for event in _active_events(sample):
        if event.origin != "reviewer":
            continue
        state = _event_state(event, claim)
        if state is not None:
            states.setdefault(event.actor, set()).add(state)
    # Conflicting standing branches do not become an accepted vote by ordering them.
    return {actor for actor, values in states.items() if values == {"accepted"}}


def _require_accepted(sample: Sample, claim: Claim, policy: ReviewPolicy) -> None:
    if claim.origin != "reviewer" or claim.review != "accepted":
        raise ValueError(f"Gold needs accepted reviewer evidence for {claim.id}")
    declared = set(claim.reviewers)
    if policy.independent and claim.author is not None:
        declared.discard(claim.author)
    if policy.reviewer_ids:
        declared.intersection_update(policy.reviewer_ids)
    if len(declared) < policy.min_reviewers:
        raise ValueError(f"Gold reviewer count/independent policy is not met for {claim.id}")
    if len(declared & _accepted_actors(sample, claim)) < policy.min_reviewers:
        raise ValueError(f"Gold acceptance history is missing or revoked for {claim.id}")


def validate_detection(sample: Sample, policy: ReviewPolicy) -> None:
    for key in policy.required_groups:
        if not sample.groups.get(key):
            raise ValueError(f"Gold sample {sample.id} lacks required {key} group")
    covered_taxa: set[str] = set()
    covered_categories: set[str] = set()
    for claim in sample.completeness:
        if claim.task != "detection" or claim.status != "exhaustive":
            continue
        _require_accepted(sample, claim, policy)
        covered_taxa.update(claim.taxa)
        covered_categories.update(claim.categories)
    if not set(policy.taxa) <= covered_taxa or not set(policy.categories) <= covered_categories:
        raise ValueError("Gold completeness scope does not cover every named release target")
    for note in sample.annotations:
        if note.origin != "model" and note.label in {"present", "absent"}:
            _require_accepted(sample, note, policy)


def promote_detection(sample: Sample, policy: ReviewPolicy) -> Sample:
    """Promote only after policy validation, preserving the original record and history."""
    validate_detection(sample, policy)
    data = sample.model_dump(mode="json")
    data["tasks"] = sorted(sample.tasks | {"detection"})
    return Sample.model_validate(data)
