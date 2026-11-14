"""Reviewer effort from timed decisions: the cost side of the pilot's discovery yield.

Only decisions the review app timed are counted. Unmeasured decisions are reported
separately rather than treated as zero effort.
"""

from collections import defaultdict
from typing import Any

MEANING = (
    "Active, visible review time per decision, paused after 10 minutes without input. "
    "'Confirmed' means a reviewer saw the suggested species; it is not a measure of "
    "useful findings, novelty or field value."
)


def _minutes(seconds: float) -> float:
    return round(seconds / 60, 2)


def summarize_effort(photos: list[dict[str, Any]], history: list[dict[str, Any]]) -> dict:
    cohort = {photo["id"]: photo["cohort"] for photo in photos}
    by_status: dict[str, float] = defaultdict(float)
    by_reviewer: dict[str, float] = defaultdict(float)
    incidental = 0.0
    measured = unmeasured = 0
    for entry in history:
        for event in entry["events"]:
            seconds = event.get("effort_seconds")
            if seconds is None:
                unmeasured += 1
                continue
            measured += 1
            by_status[event["status"]] += seconds
            by_reviewer[event["reviewer"] or "not recorded"] += seconds
            if cohort.get(entry["photo_id"]) == "incidental":
                incidental += seconds
    confirmed = sum(
        1
        for photo in photos
        if photo["cohort"] == "incidental" and photo["review_status"] == "confirmed"
    )
    return {
        "meaning": MEANING,
        "measured_decisions": measured,
        "unmeasured_decisions": unmeasured,
        "total_minutes": _minutes(sum(by_status.values())),
        "minutes_by_status": {key: _minutes(value) for key, value in by_status.items()},
        "minutes_by_reviewer": {key: _minutes(value) for key, value in by_reviewer.items()},
        "incidental_minutes": _minutes(incidental),
        "confirmed_incidental_photos": confirmed,
        "incidental_minutes_per_confirmed_photo": (
            _minutes(incidental / confirmed) if confirmed else None
        ),
    }
