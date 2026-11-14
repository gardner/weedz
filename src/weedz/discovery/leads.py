"""Leads the team selects for follow-up, by name and with a reason (PRD Journey 4).

A lead is a photo's suggested species or one of its recorded plants. Selecting and
deselecting are appended events, never edits: the latest event for a lead is where it
stands, and the history keeps who changed it and why. Only selected leads are packaged.
"""

from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

from weedz.discovery.records import ReviewerName

TABLE = """
CREATE TABLE IF NOT EXISTS lead_selections (
    id INTEGER PRIMARY KEY, run_id TEXT NOT NULL, photo_id TEXT NOT NULL,
    finding_id INTEGER REFERENCES findings(id), action TEXT NOT NULL,
    reason TEXT NOT NULL, selector TEXT NOT NULL, created_at TEXT NOT NULL,
    FOREIGN KEY(run_id, photo_id) REFERENCES photos(run_id, id)
);
"""
Action = Literal["selected", "deselected"]


class LeadEvent(BaseModel):
    """Select a lead for follow-up, or deselect it, saying why."""

    # The recorded plant (a finding's id); None is the photo's suggested species.
    finding_id: int | None = None
    action: Action
    selector: ReviewerName
    reason: str = Field(max_length=4000)

    @field_validator("reason")
    @classmethod
    def says_why(cls, reason: str) -> str:
        if not reason.strip():
            raise ValueError("Say why this lead is, or is no longer, worth follow-up")
        return reason


# The insert itself checks the event changes where the lead stands, so two people
# selecting the same lead at once cannot both succeed.
INSERT_CHANGE = """
INSERT INTO lead_selections(run_id,photo_id,finding_id,action,reason,selector,created_at)
SELECT ?,?,?,?,?,?,? WHERE COALESCE((
    SELECT action FROM lead_selections WHERE run_id=? AND photo_id=? AND finding_id IS ?
    ORDER BY id DESC LIMIT 1
), 'deselected') != ?
"""


def record_lead(store: Any, run_id: str, photo_id: str, event: LeadEvent) -> bool:
    """Append a selection event unless the lead already stands that way; whether it was
    recorded. `store` is a `Store`, untyped to avoid an import cycle."""
    target = (run_id, photo_id, event.finding_id)
    with store.connect() as db:
        cursor = db.execute(
            INSERT_CHANGE,
            (
                *target,
                event.action,
                event.reason,
                event.selector,
                datetime.now(UTC).isoformat(),
                *target,
                event.action,
            ),
        )
    return cursor.rowcount == 1


def selections(store: Any, run_id: str) -> list[dict[str, Any]]:
    """Every selection event in the run, oldest first."""
    with store.connect() as db:
        rows = db.execute(
            "SELECT * FROM lead_selections WHERE run_id=? ORDER BY id", (run_id,)
        ).fetchall()
    return [dict(row) for row in rows]


def _histories(events: list[dict[str, Any]]) -> dict[tuple[str, int | None], list[dict]]:
    histories: dict[tuple[str, int | None], list[dict]] = {}
    for event in events:
        histories.setdefault((event["photo_id"], event["finding_id"]), []).append(event)
    return histories


def selected_leads(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Leads whose latest event selects them, in the order they were first selected (so a
    reselected lead keeps its place), each with the selector and reason that stand and the
    lead's full history."""
    leads = [
        history[-1] | {"history": history}
        for history in _histories(events).values()
        if history[-1]["action"] == "selected"
    ]
    return sorted(leads, key=lambda lead: lead["history"][0]["id"])


def no_leads() -> dict[str, Any]:
    return {"suggestion": None, "plants": {}}


def lead_states(events: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Each photo's selected leads for the review app: its suggestion, and plants by id."""
    states: dict[str, dict[str, Any]] = {}
    for lead in selected_leads(events):
        state = states.setdefault(lead["photo_id"], no_leads())
        standing = {key: lead[key] for key in ("selector", "reason", "created_at")}
        if lead["finding_id"] is None:
            state["suggestion"] = standing
        else:
            state["plants"][str(lead["finding_id"])] = standing
    return states
