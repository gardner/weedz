"""Pilot outcomes against the PRD's success measures, read from a run export.

Each measure states how far it can be answered yet: measured, partially measured or
not yet measurable, with the reason. An unknown value is null, never zero. Photo sets
are tallied as independent site visits, with ungrouped photos kept apart rather than
counted as independent. Nothing here is a usefulness, novelty or first-occurrence verdict.
"""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from weedz.discovery.occurrences import predates
from weedz.discovery.outcome_terms import (
    EVIDENCE_FIELDS,
    MEANING,
    MEASURED,
    NO_REVIEWS,
    NOT_YET,
    PARTIAL,
    USEFULNESS_UNJUDGED,
    Photos,
    plural,
    tally,
)
from weedz.discovery.outcome_terms import measure_result as _measure
from weedz.discovery.referrals import referral_work, summarize_referrals


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

    def _history(self, photos: Photos, kind: str) -> list[dict[str, Any]]:
        ids = {p["id"] for p in photos}
        return [
            event
            for entry in self.export["review_history"]
            if entry["photo_id"] in ids
            for event in entry.get(kind, [])
        ]

    def decisions(self, photos: Photos) -> list[dict[str, Any]]:
        return self._history(photos, "events")

    def judgements(self, photos: Photos) -> list[dict[str, Any]]:
        """Identity, location, history and novelty judgements on these photos (#18)."""
        return self._history(photos, "judgements")

    def referrals(self, photos: Photos) -> list[dict[str, Any]]:
        """Requests for specialist assessment on these photos, with their status (#20)."""
        return self._history(photos, "referrals")

    def referral_work(self, photos: Photos) -> list[dict[str, Any]]:
        return referral_work(self.referrals(photos))

    @staticmethod
    def findings(photos: Photos) -> list[dict[str, Any]]:
        """Plants reviewers recorded: corrected species and additions the screening missed."""
        return [finding for p in photos for finding in p.get("findings", [])]

    def work(self) -> tuple[Callable[[Photos], list[dict[str, Any]]], ...]:
        """Each kind of timed review work, in the order `untimed` counts them."""
        return (self.decisions, self.findings, self.judgements, self.referral_work)

    def effort(self, photos: Photos) -> tuple[float | None, int]:
        """Measured minutes on these photos' decisions, recorded findings, judgements and
        referral actions, and how many of those were not timed."""
        return _timed([item for kind in self.work() for item in kind(photos)])

    def untimed(self, photos: Photos) -> tuple[int, ...]:
        """How many decisions, recorded findings, judgements and referral actions on these
        photos were untimed."""
        return tuple(_timed(kind(photos))[1] for kind in self.work())

    def watchlist_findings(self) -> list[tuple[dict[str, Any], str]]:
        """(photo, species) for each confirmed suggestion and recorded watchlist plant."""
        confirmed = [(p, p["scores"].get("best_species")) for p in self.confirmed]
        recorded = [
            (p, finding["species"])
            for p in self.incidental
            for finding in self.findings([p])
            if finding.get("species")
        ]
        return confirmed + recorded

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
    minutes, _ = study.effort(study.incidental)
    decisions = study.decisions(study.incidental)
    findings = study.findings(study.incidental)
    judgements = study.judgements(study.incidental)
    referral_actions = study.referral_work(study.incidental)
    untimed, untimed_findings, untimed_judgements, untimed_referrals = study.untimed(
        study.incidental
    )
    audit_minutes, untimed_audits = study.audit_effort()
    return _measure(
        "reviewer_effort_per_useful_finding",
        NOT_YET,
        "No useful finding can be counted until usefulness is judged (#18).",
        evidence={
            "incidental_minutes": minutes,
            "timed_incidental_decisions": len(decisions) - untimed,
            "untimed_incidental_decisions": untimed,
            "timed_incidental_findings": len(findings) - untimed_findings,
            "untimed_incidental_findings": untimed_findings,
            "timed_incidental_judgements": len(judgements) - untimed_judgements,
            "untimed_incidental_judgements": untimed_judgements,
            "timed_incidental_referral_actions": len(referral_actions) - untimed_referrals,
            "untimed_incidental_referral_actions": untimed_referrals,
            "audit_minutes": audit_minutes,
            "untimed_audit_answers": untimed_audits,
            "confirmed_visible": tally(study.confirmed),
        },
    )


def missed_targets(study: Study) -> dict[str, Any]:
    """Weeds the blind audit found, with their rank and top suggestion. Calling one a miss
    needs a detection rule (#16), so this reports evidence, never a miss count."""
    audit = study.export["audit"]
    key = "missed_visible_targets"
    evidence = {
        name: audit[name]
        for name in ["sampled", "audited", "found_as_top_suggestion", "found_not_top_suggestion"]
        + ["disputed", "unsure", "not_blind"]
    }
    added = [
        p
        for p in study.incidental
        if any(f["kind"] == "addition" and f.get("species") for f in study.findings([p]))
    ]
    # Reviewers saw the suggestion first, so these are not blind and never a miss rate.
    evidence["reviewer_added_watchlist_plants_not_blind"] = tally(added)
    if not audit["sampled"]:
        return _measure(key, NOT_YET, "There are no incidental photos to audit.", evidence=evidence)
    if not audit["audited"]:
        reason = f"The blind audit sample ({audit['sampled']} photos) is not yet audited."
        return _measure(key, NOT_YET, reason, evidence=evidence)
    findings = audit["findings"]
    if audit["unsure"] == audit["audited"] and not findings:
        reason = "Every audited photo had an 'unsure' answer and no weed was found."
        return _measure(key, NOT_YET, reason, evidence=evidence)
    found = {f["photo_id"] for f in findings}
    evidence["weeds_found"] = tally([p for p in study.incidental if p["id"] in found])
    evidence["findings"] = [
        {name: f[name] for name in ["photo_id", "species", "queue_rank", "queue_size"]}
        | {"top_suggestion": f["top_suggestion"]}
        for f in sorted(findings, key=lambda f: (f["queue_rank"], f["species"]))
    ]
    caveats = [
        "No detection rule is agreed yet (#16), so weeds the audit found are reported "
        "with their queue rank and top suggestion, not as hits or misses."
    ]
    if audit["remaining"]:
        caveats.append(f"{audit['audited']} of {audit['sampled']} sampled photos audited.")
    if audit["disputed"]:
        caveats.append(f"{plural(audit['disputed'], 'audited photo')} had disputed findings.")
    if audit["unsure"]:
        caveats.append(f"{plural(audit['unsure'], 'audited photo')} had an 'unsure' answer.")
    return _measure(
        key,
        PARTIAL,
        " ".join(caveats),
        denominator={"photos": audit["audited"]},
        evidence=evidence,
    )


def _comparison(photo: dict[str, Any], species: str) -> dict[str, Any] | None:
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
    candidates = study.watchlist_findings()
    if not candidates:
        reason = "There is no confirmed or recorded watchlist finding to compare yet."
        return _measure(key, NOT_YET, reason, evidence=evidence)
    compared = [(p, found) for p, species in candidates if (found := _comparison(p, species))]
    evidence["not_compared"] = len(candidates) - len(compared)
    if not compared:
        reason = "No confirmed finding has a location precise enough to compare."
        return _measure(key, NOT_YET, reason, evidence=evidence)
    evidence["radius_m"] = sorted({found["radius_m"] for _, found in compared})
    unrecorded = [p for p, found in compared if found["within_radius"] == 0]
    earlier = [p for p, found in compared if predates(p, found)]
    evidence["no_record_nearby"] = tally(unrecorded)
    evidence["earlier_than_nearby_records"] = tally(earlier)
    reason = (
        "Counts confirmed suggestions and recorded watchlist findings with no declared "
        "record within the radius, or observed in an earlier year than every record within "
        "it, as of the snapshot date. The reference set is incomplete, so this is not a "
        "novelty or first-occurrence claim "
        f"(#25). {USEFULNESS_UNJUDGED}"
    )
    return _measure(
        key,
        PARTIAL,
        reason,
        value=tally(unrecorded + earlier),
        denominator=tally([p for p, _ in compared]),
        evidence=evidence,
    )


UNTIMED = ["decisions", "findings", "judgements", "referral_actions"]


def false_alarms(study: Study) -> dict[str, Any]:
    """Rejected and inconclusive reviews and their time. Every photo shows a top suggestion
    and no rule yet decides which are proposed leads (#16), so this is not a count of
    false alarms."""
    if not study.reviewed:
        return _measure("false_alarm_workload", NOT_YET, NO_REVIEWS)
    rejected = [p for p in study.reviewed if p["review_status"] == "rejected" and not p["disputed"]]
    inconclusive = [p for p in study.reviewed if p["review_status"] == "uncertain" or p["disputed"]]
    minutes, _ = study.effort(rejected + inconclusive)
    counts = study.untimed(rejected + inconclusive)
    caveats = [
        "No rule yet decides which suggestions are proposed leads (#16), so rejected and "
        "inconclusive reviews are reported rather than a false-alarm count.",
        *study.unreviewed_note(),
    ]
    nouns = ["decision", "recorded finding", "judgement", "referral action"]
    parts = [plural(count, noun) for count, noun in zip(counts, nouns, strict=True) if count]
    if parts:
        listed = parts[-1] if len(parts) == 1 else f"{', '.join(parts[:-1])} and {parts[-1]}"
        verb = "was" if sum(counts) == 1 else "were"
        caveats.append(f"{listed} {verb} not timed, so minutes are a lower bound.")
    return _measure(
        "false_alarm_workload",
        PARTIAL,
        " ".join(caveats),
        denominator=tally(study.reviewed),
        evidence={
            "rejected": tally(rejected),
            "inconclusive": tally(inconclusive),
            "rejected_or_inconclusive_with_positive_margin": tally(
                [p for p in rejected + inconclusive if p["scores"].get("margin", 0) > 0]
            ),
            "minutes": minutes,
            **{f"untimed_{kind}": count for kind, count in zip(UNTIMED, counts, strict=True)},
        },
    )


def follow_up(study: Study) -> dict[str, Any]:
    """Specialist referrals on incidental photos (#20). A referral asks for assessment;
    whether a lead then supports a site visit or record update is not recorded yet."""
    unrecorded = (
        "Intended users' judgements of whether a lead supports a next step are not "
        "recorded yet (#18, #27)."
    )
    referrals = study.referrals(study.incidental)
    if not referrals:
        return _measure("follow_up_usefulness", NOT_YET, f"No referrals yet. {unrecorded}")
    waiting = [
        p
        for p in study.incidental
        if any(item["status"] == "open" for item in study.referrals([p]))
    ]
    reason = (
        "Counts requests for specialist assessment and how soon they were answered; an "
        f"answer is the specialist's note, not a verified identification. {unrecorded}"
    )
    return _measure(
        "follow_up_usefulness",
        PARTIAL,
        reason,
        evidence={
            "referrals": summarize_referrals(referrals),
            "photos_with_open_referrals": tally(waiting),
        },
    )


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
