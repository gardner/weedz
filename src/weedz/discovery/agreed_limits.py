"""Outcome measures against the study's agreed limits, and its review budget's use.

A verdict needs both an agreed limit and a value the measure gives in the limit's unit.
Without a limit there is no verdict; without a comparable value the limit is "not
comparable", with the measure's own reason. A value that can only grow as work goes on
(a lower bound) gives a verdict only when it already settles the limit.
"""

from typing import Any

from weedz.discovery.records import RunSpec
from weedz.discovery.study import (
    LIMITS,
    Limit,
    LimitTerms,
    StudyDefinition,
    budget_use,
    differences,
    open_decisions,
)

Quantity = tuple[float, bool]  # the value in the limit's unit, and whether a lower bound
NOT_AGREED = "No limit is agreed for this measure, so no verdict is given."
UNMEASURED = [
    "unmeasured_decisions",
    "unmeasured_findings",
    "unmeasured_judgements",
    "unmeasured_referral_actions",
]


def _share(item: dict[str, Any]) -> float | None:
    value, denominator = item["value"], item["denominator"]
    if not value or not denominator or not denominator["photos"]:
        return None
    return round(100 * value["photos"] / denominator["photos"], 1)


def _complete(item: dict[str, Any]) -> Quantity | None:
    """Evidence fields do not change with review, so the share is exact."""
    share = _share(item)
    return None if share is None else (share, False)


def _reviewed(item: dict[str, Any]) -> Quantity | None:
    """Coverage only grows while photos wait for review, so until then it is a lower bound."""
    share = _share(item)
    waiting = share is not None and item["value"]["photos"] < item["denominator"]["photos"]
    return None if share is None else (share, waiting)


# Measures that give a value in their limit's unit today. Usefulness (#18), a detection
# rule (#16) and follow-up judgements are not recorded yet, so the others give none.
QUANTITIES = {"evidence_completeness": _complete, "coverage": _reviewed}


def _verdict(terms: LimitTerms, limit: Limit, quantity: Quantity) -> tuple[str, str]:
    value, lower_bound = quantity
    at_least = terms.direction == "at least"
    met = value >= limit.value if at_least else value <= limit.value
    if lower_bound and met != at_least:
        return (
            "not comparable",
            f"Only a lower bound is measured ({value:g} {terms.unit}), which does not "
            "settle the limit yet.",
        )
    return ("met" if met else "not met"), ""


def compare(
    item: dict[str, Any], limit: Limit | None, terms: LimitTerms, quantity: Quantity | None
) -> dict[str, Any]:
    """One measure's agreed limit, its comparable value and the verdict, if any."""
    result = {
        "agreed": limit.value if limit else None,
        "direction": terms.direction,
        "unit": terms.unit,
        "note": limit.note if limit else "",
        "measured": quantity[0] if quantity else None,
    }
    if limit is None:
        return result | {"verdict": "not agreed", "reason": NOT_AGREED}
    if quantity is None:
        reason = f"This measure gives no value in this unit yet. {item['reason'] or ''}"
        return result | {"verdict": "not comparable", "reason": reason.strip()}
    verdict, reason = _verdict(terms, limit, quantity)
    return result | {"verdict": verdict, "reason": reason}


def with_limit(item: dict[str, Any], study: StudyDefinition | None) -> dict[str, Any]:
    key = item["key"]
    limit = study.limits.get(key) if study else None
    quantity = QUANTITIES[key](item) if key in QUANTITIES else None
    return item | {"limit": compare(item, limit, LIMITS[key], quantity)}


def spent(export: dict[str, Any]) -> tuple[float, int, int]:
    """Measured review minutes (decisions, findings, judgements, referrals and blind
    audits), how many actions were untimed, and how many photos had a decision or audit."""
    effort = export.get("review_effort") or {}
    audits = [event for entry in export.get("audit_history", []) for event in entry["events"]]
    seconds = [event.get("effort_seconds") for event in audits]
    minutes = effort.get("total_minutes", 0) + sum(s for s in seconds if s is not None) / 60
    untimed = sum(effort.get(key, 0) for key in UNMEASURED) + seconds.count(None)
    worked = {
        entry["photo_id"]
        for kind in ("review_history", "audit_history")
        for entry in export.get(kind, [])
        if entry.get("events")
    }
    return minutes, untimed, len(worked)


def study_budget(export: dict[str, Any], study: StudyDefinition) -> dict[str, Any]:
    minutes, untimed, photos = spent(export)
    return budget_use(study.review_budget, minutes, untimed, photos)


def _spec(export: dict[str, Any]) -> RunSpec | None:
    saved = export["run"].get("spec")
    return RunSpec.from_saved(saved) if saved else None


def study_summary(export: dict[str, Any], study: StudyDefinition | None) -> dict[str, Any] | None:
    """The linked study as the outcomes report states it; None when no study is linked."""
    linked = export.get("study")
    if not linked or study is None:
        return None
    return {
        "id": linked["id"],
        "version": linked["version"],
        "author": linked["author"],
        "created_at": linked["created_at"],
        "status": study.status,
        "question": study.question,
        "partner": study.partner,
        "open_decisions": open_decisions(study),
        "differences": differences(study, _spec(export)),
        "budget_use": study_budget(export, study),
    }
