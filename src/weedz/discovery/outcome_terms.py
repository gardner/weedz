"""Shared terms of the pilot outcomes report: statuses, success conditions and tallies."""

from collections.abc import Callable
from typing import Any

from weedz.discovery.limits import search_area

MEASURED = "measured"
PARTIAL = "partially measured"
NOT_YET = "not yet measurable"

Photos = list[dict[str, Any]]

MEANING = (
    "How far this run answers each pilot success measure (docs/prd.md). Values are "
    "counts of photos, independent site visits and ungrouped photos that could not be "
    "grouped; 'unknown' means not measured, not zero. No numeric success limits have "
    "been agreed yet, so there are no pass or fail verdicts."
)
NO_REVIEWS = "No incidental photo has been reviewed yet."
USEFULNESS_UNJUDGED = (
    "A confirmed review records only that the suggested species is visible; whether a "
    "finding is useful is not judged separately yet (#18)."
)
CONDITIONS = {
    "useful_incidental_yield": (
        "Useful incidental yield",
        "Produces leads the partner considers worth investigation, beyond a study "
        "consisting only of known target observations",
    ),
    "reviewer_effort_per_useful_finding": (
        "Reviewer effort per useful finding",
        "Fits the partner's agreed review capacity and improves on comparable manual searching",
    ),
    "missed_visible_targets": (
        "Missed visible targets",
        "Meets watchlist- and condition-specific limits agreed before the pilot",
    ),
    "novel_or_earlier_evidence": (
        "Novel or earlier evidence",
        "Supports defensible claims of added information rather than unsupported "
        "first-occurrence claims",
    ),
    "false_alarm_workload": (
        "False-alarm workload",
        "Does not overwhelm review capacity or erase discovery value",
    ),
    "follow_up_usefulness": (
        "Follow-up usefulness",
        "Supports specialist assessment, a meaningful site visit, or a justified "
        "historical record update",
    ),
    "evidence_completeness": (
        "Evidence and review completeness",
        "Every lead communicates the evidence and limits behind its conclusion",
    ),
    "coverage": (
        "Coverage and review usability",
        "Users can complete the core journey and explain which evidence remains unassessed",
    ),
}
EVIDENCE_FIELDS: dict[str, Callable[[dict[str, Any]], bool]] = {
    "source": lambda p: bool(p.get("source_url")),
    "attribution": lambda p: bool(p.get("attribution")),
    "licence": lambda p: bool(p.get("photo_license")) and bool(p.get("observation_license")),
    "date": lambda p: bool(p.get("observed_on")),
    # A location is complete when it gives a search area (weedz.discovery.limits).
    "location": lambda p: search_area(p).status == "searchable",
    "checksum": lambda p: bool(p.get("sha256")),
}


def tally(photos: Photos) -> dict[str, int]:
    """Distinct photos, the independent site visits among groupable ones, and those left
    ungrouped."""
    photos = list({p["id"]: p for p in photos}.values())
    return {
        "photos": len(photos),
        "site_visits": len({p["encounter_group"] for p in photos if p["encounter_linkable"]}),
        "ungrouped_photos": sum(not p["encounter_linkable"] for p in photos),
    }


def plural(count: int, noun: str) -> str:
    return f"{count} {noun}{'' if count == 1 else 's'}"


def measure_result(
    key: str,
    status: str,
    reason: str | None,
    value: Any = None,
    denominator: Any = None,
    evidence: dict[str, Any] | None = None,
) -> dict[str, Any]:
    name, condition = CONDITIONS[key]
    return {
        "key": key,
        "measure": name,
        "status": status,
        "reason": reason,
        "value": value,
        "denominator": denominator,
        "evidence": evidence or {},
        "success_condition": condition,
    }
