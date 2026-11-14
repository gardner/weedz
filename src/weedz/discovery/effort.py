"""Reviewer effort from timed decisions: the cost side of the pilot's discovery yield.

Only decisions the review app timed are counted. Unmeasured decisions are reported
separately rather than treated as zero effort.
"""

from collections import defaultdict
from typing import Any

MEANING = (
    "Active, visible review time per decision, paused after 10 minutes without input. "
    "A photo counts as 'confirmed' only when every reviewer's latest decision says "
    "the suggested species is visible; disputed photos are not counted. It is not a "
    "measure of useful findings, novelty or field value."
)


def _minutes(seconds: float) -> float:
    return round(seconds / 60, 2)


def summarize_effort(photos: list[dict[str, Any]], history: list[dict[str, Any]]) -> dict:
    cohort = {photo["id"]: photo["cohort"] for photo in photos}
    by_status: dict[str, float] = defaultdict(float)
    by_reviewer: dict[str, float] = defaultdict(float)
    incidental = 0.0
    measured = unmeasured = unmeasured_incidental = 0
    for entry in history:
        is_incidental = cohort.get(entry["photo_id"]) == "incidental"
        for event in entry["events"]:
            seconds = event.get("effort_seconds")
            if seconds is None:
                unmeasured += 1
                unmeasured_incidental += is_incidental
                continue
            measured += 1
            by_status[event["status"]] += seconds
            by_reviewer[event["reviewer"] or "not recorded"] += seconds
            if is_incidental:
                incidental += seconds
    # Undisputed, so every reviewer's latest decision agrees with the latest status.
    confirmed = sum(
        1
        for photo in photos
        if photo["cohort"] == "incidental"
        and photo["review_status"] == "confirmed"
        and not photo["disputed"]
    )
    return {
        "meaning": MEANING,
        "measured_decisions": measured,
        "unmeasured_decisions": unmeasured,
        "total_minutes": _minutes(sum(by_status.values())),
        "minutes_by_status": {key: _minutes(value) for key, value in by_status.items()},
        "minutes_by_reviewer": {key: _minutes(value) for key, value in by_reviewer.items()},
        "incidental_minutes": _minutes(incidental),
        "unmeasured_incidental_decisions": unmeasured_incidental,
        "confirmed_incidental_photos": confirmed,
        # Untimed incidental decisions would make the rate look cheaper than it was.
        "incidental_minutes_per_confirmed_photo": (
            _minutes(incidental / confirmed) if confirmed and not unmeasured_incidental else None
        ),
    }
