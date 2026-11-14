"""Pilot outcomes are read from a run export, one success measure at a time."""

from typing import Any

from weedz.discovery.outcomes import MEASURED, NOT_YET, PARTIAL, outcomes, to_markdown

SNAPSHOT = {"retrieved_at": "2026-11-14T05:04:00+00:00", "counts": {"Ulex europaeus": 147}}


def photo(pid: str, group: str | None = None, **fields: Any) -> dict[str, Any]:
    """An incidental photo; `group` makes it linkable to that site visit, else ungrouped."""
    return {
        "id": pid,
        "cohort": "incidental",
        "encounter_group": group or pid,
        "encounter_linkable": group is not None,
        "review_status": "unreviewed",
        "disputed": False,
        "scores": {"best_species": "Ulex europaeus", "margin": 0.01},
        "source_url": f"https://example.org/{pid}",
        "attribution": "Observer (CC BY)",
        "photo_license": "cc-by",
        "observation_license": "cc-by",
        "observed_on": "2024-01-01",
        "coordinate_status": "public",
        "positional_accuracy_m": 10.0,
        "sha256": "abc",
    } | fields


def event(status: str, seconds: float | None) -> dict[str, Any]:
    return {"status": status, "reviewer": "Ana", "effort_seconds": seconds}


def audit(**counts: Any) -> dict[str, Any]:
    base = {"sampled": 2, "audited": 0, "remaining": 2, "weed_found": 0}
    base |= {"found_as_top_suggestion": 0, "found_not_top_suggestion": 0}
    return base | {"not_blind": 0, "disputed": 0, "unsure": 0, "findings": []} | counts


def export(
    photos: list[dict[str, Any]],
    history: dict[str, list[dict[str, Any]]] | None = None,
    references: dict[str, Any] | None = None,
    **extra: Any,
) -> dict[str, Any]:
    history = history or {}
    return {
        "run": {"id": "run", "model": {"model": "imageomics/bioclip", "ranking_revision": 2}},
        "photos": photos,
        "encounters": {"incidental_photos": len(photos)},
        "review_history": [
            {"photo_id": p["id"], "events": history.get(p["id"], [])} for p in photos
        ],
        "audit": audit(),
        "references": references,
        "corpus_coverage": {"photos": len(photos)},
    } | extra


def measure(report: dict[str, Any], key: str) -> dict[str, Any]:
    return next(item for item in report["measures"] if item["key"] == key)


def test_every_success_measure_is_reported_with_status_and_reason() -> None:
    report = outcomes(export([photo("a", "a")]))
    assert [item["key"] for item in report["measures"]] == [
        "useful_incidental_yield",
        "reviewer_effort_per_useful_finding",
        "missed_visible_targets",
        "novel_or_earlier_evidence",
        "false_alarm_workload",
        "follow_up_usefulness",
        "evidence_completeness",
        "coverage",
    ]
    for item in report["measures"]:
        assert item["status"] in {MEASURED, PARTIAL, NOT_YET}
        assert item["status"] == MEASURED or item["reason"]
        assert item["success_condition"]


def test_unmeasurable_measures_have_no_value_rather_than_zero() -> None:
    report = outcomes(export([photo("a", "a")]))
    for key in ["useful_incidental_yield", "missed_visible_targets", "false_alarm_workload"]:
        assert measure(report, key)["status"] == NOT_YET
        assert measure(report, key)["value"] is None


def test_photo_sets_are_tallied_as_site_visits_with_ungrouped_photos_apart() -> None:
    photos = [photo("a", "v1"), photo("b", "v1"), photo("c", "v2"), photo("d"), photo("e")]
    report = outcomes(export(photos))
    assert report["context"]["incidental"] == {"photos": 5, "site_visits": 2, "ungrouped_photos": 2}
    assert measure(report, "coverage")["denominator"]["site_visits"] == 2


def test_confirmed_reviews_are_evidence_not_useful_findings() -> None:
    photos = [photo("a", "v1", review_status="confirmed"), photo("b", "v1")]
    photos[1] |= {"review_status": "confirmed"}
    useful = measure(outcomes(export(photos)), "useful_incidental_yield")
    assert useful["status"] == NOT_YET
    assert useful["value"] is None
    assert useful["evidence"]["confirmed_visible"]["site_visits"] == 1
    assert "#18" in useful["reason"]


def test_no_reviews_yet_is_the_stated_reason() -> None:
    useful = measure(outcomes(export([photo("a", "a")])), "useful_incidental_yield")
    assert "no incidental photo has been reviewed" in useful["reason"].lower()


def test_disputed_confirmations_are_not_counted_as_visible() -> None:
    photos = [photo("a", "a", review_status="confirmed", disputed=True)]
    useful = measure(outcomes(export(photos)), "useful_incidental_yield")
    assert useful["evidence"]["confirmed_visible"]["photos"] == 0


def test_effort_per_useful_finding_waits_for_useful_findings_but_shows_minutes() -> None:
    photos = [photo("a", "a", review_status="rejected")]
    effort = measure(
        outcomes(export(photos, {"a": [event("rejected", 90)]})),
        "reviewer_effort_per_useful_finding",
    )
    assert effort["status"] == NOT_YET
    assert effort["value"] is None
    assert effort["evidence"]["incidental_minutes"] == 1.5
    assert effort["evidence"]["untimed_incidental_decisions"] == 0


def test_missed_targets_need_an_audit_and_are_partial_while_samples_remain() -> None:
    missed = measure(outcomes(export([photo("a", "a")])), "missed_visible_targets")
    assert "not yet audited" in missed["reason"]
    findings = [{"photo_id": "a", "species": "Ulex europaeus", "top_suggestion": False}]
    findings[0] |= {"queue_rank": 2, "queue_size": 2}
    partial = audit(audited=1, remaining=1, weed_found=1, found_not_top_suggestion=1)
    partial["findings"] = findings
    photos = [photo("a", "v1"), photo("b", "v2")]
    missed = measure(outcomes(export(photos, audit=partial)), "missed_visible_targets")
    assert missed["status"] == PARTIAL
    assert missed["value"] == {"photos": 1, "site_visits": 1, "ungrouped_photos": 0}
    assert missed["denominator"] == {"photos": 1}
    assert "1 of 2" in missed["reason"]
    assert missed["evidence"]["queue_ranks_not_top"] == [2]


def test_a_run_without_incidental_photos_has_nothing_to_audit() -> None:
    empty = audit(sampled=0, remaining=0)
    missed = measure(outcomes(export([], audit=empty)), "missed_visible_targets")
    assert missed["reason"] == "There are no incidental photos to audit."


def test_a_fully_audited_undisputed_sample_is_measured() -> None:
    done = audit(sampled=1, audited=1, remaining=0)
    missed = measure(outcomes(export([photo("a", "a")], audit=done)), "missed_visible_targets")
    assert missed["status"] == MEASURED
    assert missed["value"] == {"photos": 0, "site_visits": 0, "ungrouped_photos": 0}


def test_novelty_needs_a_reference_snapshot() -> None:
    photos = [photo("a", "a", review_status="confirmed")]
    novel = measure(outcomes(export(photos)), "novel_or_earlier_evidence")
    assert novel["status"] == NOT_YET
    assert "no reference snapshot" in novel["reason"]


def test_novelty_is_distance_to_declared_records_never_a_claim() -> None:
    near = {"Ulex europaeus": {"comparable": True, "within_radius": 2, "radius_m": 5000.0}}
    far = {"Ulex europaeus": {"comparable": True, "within_radius": 0, "radius_m": 5000.0}}
    hidden = {"Ulex europaeus": {"comparable": False, "reason": "obscured"}}
    photos = [
        photo("a", "v1", review_status="confirmed", reference_comparison=near),
        photo("b", "v2", review_status="confirmed", reference_comparison=far),
        photo("c", review_status="confirmed", reference_comparison=hidden),
    ]
    novel = measure(outcomes(export(photos, references=SNAPSHOT)), "novel_or_earlier_evidence")
    assert novel["status"] == PARTIAL
    assert novel["value"] == {"photos": 1, "site_visits": 1, "ungrouped_photos": 0}
    assert novel["denominator"] == {"photos": 2, "site_visits": 2, "ungrouped_photos": 0}
    assert novel["evidence"]["not_compared"] == 1
    assert novel["evidence"]["reference_as_of"] == SNAPSHOT["retrieved_at"]
    assert "not a novelty" in novel["reason"]


def test_novelty_with_a_snapshot_but_no_findings_is_not_yet_measurable() -> None:
    novel = measure(
        outcomes(export([photo("a", "a")], references=SNAPSHOT)), "novel_or_earlier_evidence"
    )
    assert novel["status"] == NOT_YET
    assert "no confirmed incidental finding" in novel["reason"]


def test_false_alarms_count_rejected_uncertain_and_disputed_leads_with_their_time() -> None:
    photos = [
        photo("a", "v1", review_status="rejected"),
        photo("b", "v2", review_status="uncertain"),
        photo("c", "v3", review_status="confirmed", disputed=True),
        photo("d", "v4", review_status="confirmed"),
    ]
    history = {
        "a": [event("rejected", 60)],
        "b": [event("uncertain", 30), event("uncertain", None)],
        "c": [event("confirmed", 30), event("rejected", 60)],
        "d": [event("confirmed", 600)],
    }
    alarms = measure(outcomes(export(photos, history)), "false_alarm_workload")
    assert alarms["value"]["site_visits"] == 3
    assert alarms["denominator"]["site_visits"] == 4
    assert alarms["evidence"]["minutes"] == 3.0
    assert alarms["evidence"]["untimed_decisions"] == 1
    assert alarms["status"] == PARTIAL
    assert "lower bound" in alarms["reason"]


def test_false_alarms_are_measured_when_every_lead_is_reviewed_and_timed() -> None:
    photos = [photo("a", "a", review_status="rejected")]
    alarms = measure(
        outcomes(export(photos, {"a": [event("rejected", 60)]})), "false_alarm_workload"
    )
    assert alarms["status"] == MEASURED


def test_follow_up_usefulness_is_not_recorded_yet() -> None:
    follow_up = measure(outcomes(export([photo("a", "a")])), "follow_up_usefulness")
    assert follow_up["status"] == NOT_YET
    assert follow_up["value"] is None


def test_evidence_completeness_names_what_is_missing() -> None:
    photos = [
        photo("a", "a", review_status="rejected"),
        photo("b", positional_accuracy_m=None),
        photo("c", observed_on=None, coordinate_status="obscured"),
    ]
    complete = measure(outcomes(export(photos)), "evidence_completeness")
    assert complete["value"]["photos"] == 1
    assert complete["denominator"]["photos"] == 3
    assert complete["evidence"]["missing"] == {"date": 1, "location": 2}
    assert complete["evidence"]["with_decision"] == 1
    assert complete["status"] == PARTIAL
    assert "2 of 3" in complete["reason"]


def test_coverage_counts_assessed_and_unassessed_visits() -> None:
    photos = [photo("a", "v1", review_status="rejected"), photo("b", "v2"), photo("c")]
    coverage = measure(outcomes(export(photos)), "coverage")
    assert coverage["value"] == {"photos": 1, "site_visits": 1, "ungrouped_photos": 0}
    assert coverage["evidence"]["unassessed"] == {
        "photos": 2,
        "site_visits": 1,
        "ungrouped_photos": 1,
    }
    assert coverage["status"] == PARTIAL


def test_reference_and_lookalike_photos_are_not_incidental_leads() -> None:
    photos = [photo("a", "a"), photo("r", "r", cohort="reference", review_status="confirmed")]
    report = outcomes(export(photos))
    assert report["context"]["incidental"]["photos"] == 1
    assert measure(report, "coverage")["value"]["photos"] == 0


def test_markdown_shows_every_measure_and_never_prints_unknown_as_zero() -> None:
    text = to_markdown(outcomes(export([photo("a", "a"), photo("b")])))
    assert "# Pilot outcomes: run" in text
    assert "Useful incidental yield" in text
    assert "not yet measurable" in text
    assert "1 site visit + 1 ungrouped photo" in text
    assert "| Useful incidental yield | not yet measurable | unknown |" in text


def test_minutes_are_unknown_rather_than_zero_when_nothing_was_timed() -> None:
    photos = [photo("a", "a", review_status="rejected")]
    report = outcomes(export(photos, {"a": [event("rejected", None)]}))
    assert measure(report, "false_alarm_workload")["evidence"]["minutes"] is None
    effort = measure(report, "reviewer_effort_per_useful_finding")["evidence"]
    assert effort["incidental_minutes"] is None
    assert effort["untimed_incidental_decisions"] == 1
