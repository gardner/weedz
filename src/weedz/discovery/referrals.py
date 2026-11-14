"""Specialist referrals: an unresolved photo or recorded plant sent for assessment.

A referral is opened with a reason, a note and the expertise it needs, then answered or
withdrawn by a further event. Nothing is edited: the lifecycle is the event history.
A specialist's answer never changes a reviewer's decision or judgement; it may cite the
judgements it informed, which are recorded separately under the specialist's name.
"""

from datetime import datetime
from statistics import median
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from weedz.discovery.records import ReviewerName

REASONS = {
    "lookalike": "A native or other lookalike is plausible",
    "cultivated_or_wild": "It may be cultivated rather than wild",
    "poor_view": "The view is too poor to judge",
    "location_or_date": "The location or date is in question",
    "other": "Another reason, given in the note",
}
Action = Literal["answered", "withdrawn"]

TABLES = """
CREATE TABLE IF NOT EXISTS referrals (
    id INTEGER PRIMARY KEY, run_id TEXT NOT NULL, photo_id TEXT NOT NULL,
    finding_id INTEGER REFERENCES findings(id), reason TEXT NOT NULL,
    expertise TEXT NOT NULL, note TEXT NOT NULL, referrer TEXT NOT NULL,
    effort_seconds REAL, created_at TEXT NOT NULL,
    FOREIGN KEY(run_id, photo_id) REFERENCES photos(run_id, id)
);
CREATE TABLE IF NOT EXISTS referral_events (
    id INTEGER PRIMARY KEY, referral_id INTEGER NOT NULL REFERENCES referrals(id),
    action TEXT NOT NULL, actor TEXT NOT NULL, note TEXT NOT NULL,
    judgement_ids TEXT NOT NULL DEFAULT '[]', effort_seconds REAL, created_at TEXT NOT NULL
);
"""


def _noted(note: str, reason: str) -> str:
    if not note.strip():
        raise ValueError(reason)
    return note


class Referral(BaseModel):
    """A request for specialist assessment of a photo, or of one recorded plant."""

    finding_id: int | None = None
    reason: Literal["lookalike", "cultivated_or_wild", "poor_view", "location_or_date", "other"]
    note: str = Field(max_length=4000)
    # Free text: there is no agreed list of specialists yet (docs/prd.md open questions).
    expertise: str = Field(default="", max_length=200)
    referrer: ReviewerName
    effort_seconds: float | None = Field(default=None, ge=0, le=86_400)

    @field_validator("note")
    @classmethod
    def says_what_is_unresolved(cls, note: str) -> str:
        return _noted(note, "Say what is unresolved and what would settle it")


class ReferralEvent(BaseModel):
    """A specialist's answer to an open referral, or its withdrawal, with the reason."""

    action: Action
    actor: ReviewerName
    note: str = Field(max_length=4000)
    # Judgements on the referred plant, made since the referral, that the answer informed.
    judgement_ids: list[int] = Field(default_factory=list, max_length=20)
    effort_seconds: float | None = Field(default=None, ge=0, le=86_400)

    @field_validator("note")
    @classmethod
    def gives_a_reason(cls, note: str) -> str:
        return _noted(note, "Give the assessment, or the reason for withdrawing, in the note")

    @model_validator(mode="after")
    def only_answers_cite_judgements(self) -> "ReferralEvent":
        if self.judgement_ids and self.action != "answered":
            raise ValueError("Only an answer can cite the judgements it informed")
        return self


def with_status(referral: dict[str, Any], events: list[dict[str, Any]]) -> dict[str, Any]:
    """A referral with its closing events (oldest first) and the status they give it."""
    status = events[-1]["action"] if events else "open"
    return referral | {"status": status, "events": events}


def uncitable(
    referral: dict[str, Any], judgements: list[dict[str, Any]], ids: list[int]
) -> str | None:
    """Why an answer cannot cite these judgements, or None. Each must be on the referred
    plant (any plant when the whole photo was referred) and made since the referral."""
    known = {judgement["id"]: judgement for judgement in judgements}
    for judgement_id in ids:
        judgement = known.get(judgement_id)
        if judgement is None:
            return f"Judgement {judgement_id} is not on this photo"
        target = referral["finding_id"]
        if target is not None and judgement["finding_id"] != target:
            return f"Judgement {judgement_id} is about a different plant from the referral"
        if judgement["created_at"] < referral["created_at"]:
            return f"Judgement {judgement_id} was made before the referral"
    return None


def _hours(start: str, end: str) -> float:
    elapsed = datetime.fromisoformat(end) - datetime.fromisoformat(start)
    return round(elapsed.total_seconds() / 3600, 2)


def referral_work(referrals: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Each referral and closing event as attributed, possibly timed, reviewer work."""
    work = []
    for referral in referrals:
        work.append(
            {
                "action": "referred",
                "reviewer": referral["referrer"],
                "effort_seconds": referral["effort_seconds"],
            }
        )
        work += [
            {"action": event["action"], "reviewer": event["actor"]}
            | {"effort_seconds": event["effort_seconds"]}
            for event in referral["events"]
        ]
    return work


def summarize_referrals(referrals: list[dict[str, Any]]) -> dict[str, Any]:
    """Counts by status and reason, and hours from referral to answer (None if none)."""
    by_status = {status: 0 for status in ("open", "answered", "withdrawn")}
    by_reason: dict[str, int] = {}
    turnaround = []
    for referral in referrals:
        by_status[referral["status"]] += 1
        by_reason[referral["reason"]] = by_reason.get(referral["reason"], 0) + 1
        if referral["status"] == "answered":
            turnaround.append(_hours(referral["created_at"], referral["events"][-1]["created_at"]))
    hours = {"median": median(turnaround), "longest": max(turnaround)} if turnaround else None
    return {"referred": len(referrals), **by_status, "by_reason": by_reason} | {
        "answer_turnaround_hours": hours
    }
