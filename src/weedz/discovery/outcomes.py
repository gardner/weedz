"""Pilot outcomes against the PRD's success measures, read from a run export.

Each measure states how far it can be answered yet: measured, partially measured or
not yet measurable, with the reason. An unknown value is null, never zero. Photo sets
are tallied as independent site visits, with ungrouped photos kept apart rather than
counted as independent. Nothing here is a usefulness, novelty or first-occurrence verdict.
"""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

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
    "location": lambda p: (
        p.get("coordinate_status") == "public" and p.get("positional_accuracy_m") is not None
    ),
    "checksum": lambda p: bool(p.get("sha256")),
}


def tally(photos: Photos) -> dict[str, int]:
    """Photos, the independent site visits among groupable ones, and those left ungrouped."""
    return {
        "photos": len(photos),
        "site_visits": len({p["encounter_group"] for p in photos if p["encounter_linkable"]}),
        "ungrouped_photos": sum(not p["encounter_linkable"] for p in photos),
    }


def _minutes(seconds: float) -> float:
    return round(seconds / 60, 2)


def _timed(events: list[dict[str, Any]]) -> tuple[float | None, int]:
    """Minutes across timed events (None if none was timed) and the count left untimed."""
    seconds = [event.get("effort_seconds") for event in events]
    timed = [s for s in seconds if s is not None]
    return (_minutes(sum(timed)) if timed else None), seconds.count(None)


@dataclass(frozen=True)
class Study:
    export: dict[str, Any]

    @property
    def incidental(self) -> Photos:
        return [p for p in self.export["photos"] if p["cohort"] == "incidental"]

    @property
    def reviewed(self) -> Photos:
        return [p for p in self.incidental if p["review_status"] != "unreviewed"]

    @property
    def confirmed(self) -> Photos:
        """Undisputed confirmations: every reviewer says the suggested species is visible."""
        return [
            p for p in self.incidental if p["review_status"] == "confirmed" and not p["disputed"]
        ]

    def events(self, photos: Photos) -> list[dict[str, Any]]:
        ids = {p["id"] for p in photos}
        return [
            event
            for entry in self.export["review_history"]
            if entry["photo_id"] in ids
            for event in entry["events"]
        ]

    def effort(self, photos: Photos) -> tuple[float | None, int]:
        """Measured review minutes on these photos, and how many decisions were not timed."""
        return _timed(self.events(photos))

    def audit_effort(self) -> tuple[float | None, int]:
        """Measured blind-audit minutes, and how many audit answers were not timed."""
        return _timed(
            [event for entry in self.export.get("audit_history", []) for event in entry["events"]]
        )

    def unreviewed_note(self) -> list[str]:
        missing = len(self.incidental) - len(self.reviewed)
        if not missing:
            return []
        return [f"{missing} of {len(self.incidental)} incidental photos are not reviewed yet."]


def _measure(
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


def useful_yield(study: Study) -> dict[str, Any]:
    return _measure(
        "useful_incidental_yield",
        NOT_YET,
        USEFULNESS_UNJUDGED if study.reviewed else f"{NO_REVIEWS} {USEFULNESS_UNJUDGED}",
        denominator=tally(study.incidental),
        evidence={
            "reviewed": tally(study.reviewed),
            "confirmed_visible": tally(study.confirmed),
        },
    )


def effort_per_finding(study: Study) -> dict[str, Any]:
    minutes, untimed = study.effort(study.incidental)
    timed = len(study.events(study.incidental)) - untimed
    audit_minutes, untimed_audits = study.audit_effort()
    return _measure(
        "reviewer_effort_per_useful_finding",
        NOT_YET,
        "No useful finding can be counted until usefulness is judged (#18).",
        evidence={
            "incidental_minutes": minutes,
            "timed_incidental_decisions": timed,
            "untimed_incidental_decisions": untimed,
            "audit_minutes": audit_minutes,
            "untimed_audit_answers": untimed_audits,
            "confirmed_visible": tally(study.confirmed),
        },
    )


def missed_targets(study: Study) -> dict[str, Any]:
    audit = study.export["audit"]
    evidence = {
        key: audit[key]
        for key in ["sampled", "audited", "weed_found", "found_as_top_suggestion"]
        + ["disputed", "unsure", "not_blind"]
    }
    if not audit["audited"]:
        reason = (
            f"The blind audit sample ({audit['sampled']} photos) is not yet audited."
            if audit["sampled"]
            else "There are no incidental photos to audit."
        )
        return _measure("missed_visible_targets", NOT_YET, reason, evidence=evidence)
    findings = audit["findings"]
    top = {f["photo_id"] for f in findings if f["top_suggestion"]}
    missed = {f["photo_id"] for f in findings} - top
    evidence["found_queue_ranks"] = sorted({f["queue_rank"] for f in findings})
    caveats = []
    if audit["remaining"]:
        caveats.append(f"{audit['audited']} of {audit['sampled']} sampled photos audited.")
    if audit["disputed"]:
        caveats.append(f"{audit['disputed']} audited photos have disputed findings.")
    return _measure(
        "missed_visible_targets",
        PARTIAL if caveats else MEASURED,
        " ".join(caveats) or None,
        value=tally([p for p in study.incidental if p["id"] in missed]),
        denominator={"photos": audit["audited"]},
        evidence=evidence,
    )


def _comparison(photo: dict[str, Any]) -> dict[str, Any] | None:
    species = photo["scores"].get("best_species")
    found = photo.get("reference_comparison", {}).get(species)
    return found if found and found["comparable"] else None


def novel_evidence(study: Study) -> dict[str, Any]:
    references = study.export.get("references")
    key = "novel_or_earlier_evidence"
    if not references:
        reason = "There is no reference snapshot to compare against (`main.py references`)."
        return _measure(key, NOT_YET, reason)
    evidence = {
        "reference_as_of": references.get("retrieved_at"),
        "reference_records": references.get("counts", {}),
    }
    if not study.confirmed:
        reason = "There is no confirmed incidental finding to compare yet."
        return _measure(key, NOT_YET, reason, evidence=evidence)
    compared = [(p, found) for p in study.confirmed if (found := _comparison(p))]
    evidence["not_compared"] = len(study.confirmed) - len(compared)
    if not compared:
        reason = "No confirmed finding has a location precise enough to compare."
        return _measure(key, NOT_YET, reason, evidence=evidence)
    evidence["radius_m"] = sorted({found["radius_m"] for _, found in compared})
    reason = (
        "Counts confirmed findings with no declared record within the radius, as of the "
        "snapshot date. The reference set is incomplete, so this is not a novelty or "
        f"first-occurrence claim (#25). {USEFULNESS_UNJUDGED}"
    )
    return _measure(
        key,
        PARTIAL,
        reason,
        value=tally([p for p, found in compared if found["within_radius"] == 0]),
        denominator=tally([p for p, _ in compared]),
        evidence=evidence,
    )


def false_alarms(study: Study) -> dict[str, Any]:
    if not study.reviewed:
        return _measure("false_alarm_workload", NOT_YET, NO_REVIEWS)
    rejected = [p for p in study.reviewed if p["review_status"] == "rejected" and not p["disputed"]]
    inconclusive = [p for p in study.reviewed if p["review_status"] == "uncertain" or p["disputed"]]
    minutes, untimed = study.effort(rejected + inconclusive)
    caveats = study.unreviewed_note()
    if untimed:
        caveats.append(f"{untimed} decisions were not timed, so minutes are a lower bound.")
    return _measure(
        "false_alarm_workload",
        PARTIAL if caveats else MEASURED,
        " ".join(caveats) or None,
        value=tally(rejected + inconclusive),
        denominator=tally(study.reviewed),
        evidence={
            "rejected": tally(rejected),
            "inconclusive": tally(inconclusive),
            "minutes": minutes,
            "untimed_decisions": untimed,
        },
    )


def follow_up(_study: Study) -> dict[str, Any]:
    reason = (
        "Intended users' judgements of whether a lead supports a next step are not "
        "recorded yet (#18, #27)."
    )
    return _measure("follow_up_usefulness", NOT_YET, reason)


def completeness(study: Study) -> dict[str, Any]:
    photos = study.incidental
    if not photos:
        return _measure("evidence_completeness", NOT_YET, "The run has no incidental photos.")
    missing = {name: sum(not check(p) for p in photos) for name, check in EVIDENCE_FIELDS.items()}
    complete = [p for p in photos if all(check(p) for check in EVIDENCE_FIELDS.values())]
    undecided = len(photos) - len(study.reviewed)
    reason = f"{undecided} of {len(photos)} incidental photos have no review decision yet."
    return _measure(
        "evidence_completeness",
        PARTIAL if undecided else MEASURED,
        reason if undecided else None,
        value=tally(complete),
        denominator=tally(photos),
        evidence={
            "checked": list(EVIDENCE_FIELDS),
            "missing": {name: count for name, count in missing.items() if count},
            "with_decision": len(study.reviewed),
        },
    )


def coverage(study: Study) -> dict[str, Any]:
    reviewed = {p["id"] for p in study.reviewed}
    audit = study.export["audit"]
    reason = " ".join(
        [
            *study.unreviewed_note(),
            "Whether intended users can complete the study is not recorded yet.",
        ]
    )
    return _measure(
        "coverage",
        PARTIAL,
        reason,
        value=tally(study.reviewed),
        denominator=tally(study.incidental),
        evidence={
            "unassessed": tally([p for p in study.incidental if p["id"] not in reviewed]),
            "audit_sampled": audit["sampled"],
            "audit_audited": audit["audited"],
            "corpus": study.export.get("corpus_coverage", {}),
        },
    )


MEASURES = [
    useful_yield,
    effort_per_finding,
    missed_targets,
    novel_evidence,
    false_alarms,
    follow_up,
    completeness,
    coverage,
]


def outcomes(export: dict[str, Any]) -> dict[str, Any]:
    study = Study(export)
    run = export["run"]
    references = export.get("references") or {}
    return {
        "schema": 1,
        "run_id": run["id"],
        "meaning": MEANING,
        "context": {
            "model": run.get("model", {}).get("model"),
            "ranking_revision": run.get("model", {}).get("ranking_revision"),
            "incidental": tally(study.incidental),
            "site_visit_rule": export["encounters"].get("rule"),
            "reference_as_of": references.get("retrieved_at"),
        },
        "measures": [measure(study) for measure in MEASURES],
    }


def _plural(count: int, noun: str) -> str:
    return f"{count} {noun}{'' if count == 1 else 's'}"


def _render(value: Any) -> str:
    if value is None:
        return "unknown"
    if isinstance(value, dict) and "site_visits" in value:
        visits = _plural(value["site_visits"], "site visit")
        ungrouped = _plural(value["ungrouped_photos"], "ungrouped photo")
        return f"{visits} + {ungrouped} ({_plural(value['photos'], 'photo')})"
    if isinstance(value, dict) and set(value) == {"photos"}:
        return _plural(value["photos"], "photo")
    if isinstance(value, dict):
        return "; ".join(f"{key}: {_render(item)}" for key, item in value.items()) or "none"
    if isinstance(value, list):
        return ", ".join(map(str, value)) or "none"
    return str(value)


def to_markdown(report: dict[str, Any]) -> str:
    context = report["context"]
    lines = [
        f"# Pilot outcomes: {report['run_id']}",
        "",
        report["meaning"],
        "",
        f"Incidental photos: {_render(context['incidental'])}. Model: {context['model']}, "
        f"ranking revision {context['ranking_revision']}. Reference snapshot: "
        f"{context['reference_as_of'] or 'none'}.",
        "",
        "| Measure | Status | Value | Out of | Why |",
        "| --- | --- | --- | --- | --- |",
    ]
    for item in report["measures"]:
        cells = [item["measure"], item["status"], _render(item["value"])]
        cells += [_render(item["denominator"]), item["reason"] or ""]
        lines.append(f"| {' | '.join(cells)} |")
    lines += ["", "## Evidence"]
    for item in report["measures"]:
        lines += [
            "",
            f"### {item['measure']}",
            "",
            f"Success condition: {item['success_condition']}.",
        ]
        lines += [f"- {key}: {_render(value)}" for key, value in item["evidence"].items()]
    return "\n".join(lines) + "\n"
