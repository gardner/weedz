"""Reviewer effort from timed decisions, findings, judgements and referrals: the cost of
discovery.

Only the work the review app timed is counted. Unmeasured work is reported separately
rather than treated as zero effort.
"""

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

from weedz.discovery.referrals import referral_work

MEANING = (
    "Active, visible review time per decision, per recorded finding (a corrected or "
    "missed plant), per judgement (identity, location, history or novelty) and per "
    "referral action (referring, answering or withdrawing), paused after 10 minutes "
    "without input. Time spent before one of these is saved belongs to it, so decision "
    "minutes exclude it; totals include all four. A photo "
    "counts as 'confirmed' only when every reviewer's latest decision says the "
    "suggested species is visible; disputed photos are not counted. It is not a "
    "measure of useful findings, novelty or field value."
)


def _minutes(seconds: float) -> float:
    return round(seconds / 60, 2)


@dataclass
class _Tally:
    seconds: dict[str, float] = field(default_factory=lambda: defaultdict(float))
    measured: int = 0
    unmeasured: int = 0
    unmeasured_incidental: int = 0

    def minutes(self) -> dict[str, float]:
        return {key: _minutes(value) for key, value in self.seconds.items()}


def summarize_effort(photos: list[dict[str, Any]], history: list[dict[str, Any]]) -> dict:
    cohort = {photo["id"]: photo["cohort"] for photo in photos}
    findings = {photo["id"]: photo.get("findings", []) for photo in photos}
    decisions, recorded, judged, referred = _Tally(), _Tally(), _Tally(), _Tally()
    by_reviewer: dict[str, float] = defaultdict(float)
    incidental = 0.0
    for entry in history:
        is_incidental = cohort.get(entry["photo_id"]) == "incidental"
        for events, key, tally in [
            (entry["events"], "status", decisions),
            (findings.get(entry["photo_id"], []), "kind", recorded),
            (entry.get("judgements", []), "dimension", judged),
            (referral_work(entry.get("referrals", [])), "action", referred),
        ]:
            for event in events:
                seconds = event.get("effort_seconds")
                if seconds is None:
                    tally.unmeasured += 1
                    tally.unmeasured_incidental += is_incidental
                    continue
                tally.measured += 1
                tally.seconds[event[key]] += seconds
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
    tallies = (decisions, recorded, judged, referred)
    untimed = sum(tally.unmeasured_incidental for tally in tallies)
    return {
        "meaning": MEANING,
        "measured_decisions": decisions.measured,
        "unmeasured_decisions": decisions.unmeasured,
        "measured_findings": recorded.measured,
        "unmeasured_findings": recorded.unmeasured,
        "measured_judgements": judged.measured,
        "unmeasured_judgements": judged.unmeasured,
        "measured_referral_actions": referred.measured,
        "unmeasured_referral_actions": referred.unmeasured,
        "total_minutes": _minutes(sum(sum(tally.seconds.values()) for tally in tallies)),
        "minutes_by_status": decisions.minutes(),
        "minutes_by_finding_kind": recorded.minutes(),
        "minutes_by_judgement_dimension": judged.minutes(),
        "minutes_by_referral_action": referred.minutes(),
        "minutes_by_reviewer": {key: _minutes(value) for key, value in by_reviewer.items()},
        "incidental_minutes": _minutes(incidental),
        "unmeasured_incidental_decisions": decisions.unmeasured_incidental,
        "unmeasured_incidental_findings": recorded.unmeasured_incidental,
        "unmeasured_incidental_judgements": judged.unmeasured_incidental,
        "unmeasured_incidental_referral_actions": referred.unmeasured_incidental,
        "confirmed_incidental_photos": confirmed,
        # Untimed incidental work would make the rate look cheaper.
        "incidental_minutes_per_confirmed_photo": (
            _minutes(incidental / confirmed) if confirmed and not untimed else None
        ),
    }
