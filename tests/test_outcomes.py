"""Pilot outcomes are read from a run export, one success measure at a time."""

from typing import Any

from weedz.discovery.outcome_report import to_markdown
from weedz.discovery.outcomes import MEASURED, NOT_YET, PARTIAL, outcomes

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
    assert missed["value"] is None
    assert missed["denominator"] == {"photos": 1}
    assert "1 of 2" in missed["reason"]
    assert missed["evidence"]["weeds_found"] == {
        "photos": 1,
        "site_visits": 1,
        "ungrouped_photos": 0,
    }
    assert missed["evidence"]["found_not_top_suggestion"] == 1
    assert missed["evidence"]["findings"] == [
        {"photo_id": "a", "species": "Ulex europaeus", "queue_rank": 2, "queue_size": 2}
        | {"top_suggestion": False}
    ]


def test_a_run_without_incidental_photos_has_nothing_to_audit() -> None:
    empty = audit(sampled=0, remaining=0)
    missed = measure(outcomes(export([], audit=empty)), "missed_visible_targets")
    assert missed["reason"] == "There are no incidental photos to audit."


def test_misses_are_not_counted_without_an_agreed_detection_rule() -> None:
    done = audit(sampled=1, audited=1, remaining=0)
    missed = measure(outcomes(export([photo("a", "a")], audit=done)), "missed_visible_targets")
    assert missed["status"] == PARTIAL
    assert missed["value"] is None
    assert "#16" in missed["reason"]


def test_unsure_audit_answers_are_not_a_measured_zero() -> None:
    unsure = audit(sampled=2, audited=2, remaining=0, unsure=1)
    missed = measure(outcomes(export([photo("a", "a")], audit=unsure)), "missed_visible_targets")
    assert missed["status"] == PARTIAL
    assert "1 audited photo had an 'unsure' answer" in missed["reason"]
    all_unsure = audit(sampled=1, audited=1, remaining=0, unsure=1)
    missed = measure(
        outcomes(export([photo("a", "a")], audit=all_unsure)), "missed_visible_targets"
    )
    assert missed["status"] == NOT_YET
    assert missed["value"] is None


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


def test_findings_older_than_every_nearby_record_count_as_earlier_evidence() -> None:
    def nearby(earliest: int) -> dict[str, Any]:
        found = {"comparable": True, "within_radius": 3, "radius_m": 5000.0}
        return {"Ulex europaeus": found | {"earliest_year": earliest, "latest_year": 2020}}

    photos = [
        photo("a", "v1", review_status="confirmed", reference_comparison=nearby(2019)),
        photo("b", "v2", review_status="confirmed", reference_comparison=nearby(2024)),
        photo("c", "v3", review_status="confirmed", reference_comparison=nearby(2010)),
    ]
    photos[0]["observed_on"] = "2018-05-01"
    novel = measure(outcomes(export(photos, references=SNAPSHOT)), "novel_or_earlier_evidence")
    assert novel["value"] == {"photos": 1, "site_visits": 1, "ungrouped_photos": 0}
    assert novel["evidence"]["no_record_nearby"]["photos"] == 0
    assert novel["evidence"]["earlier_than_nearby_records"]["photos"] == 1


def test_a_finding_is_not_earlier_when_a_nearby_record_is_undated() -> None:
    found = {"comparable": True, "within_radius": 2, "radius_m": 5000.0, "earliest_year": 2020}
    comparison = {"Ulex europaeus": found | {"undated_within_radius": 1}}
    photos = [photo("a", "v1", review_status="confirmed", reference_comparison=comparison)]
    photos[0]["observed_on"] = "2015-01-01"
    novel = measure(outcomes(export(photos, references=SNAPSHOT)), "novel_or_earlier_evidence")
    assert novel["value"]["photos"] == 0
    assert novel["evidence"]["earlier_than_nearby_records"]["photos"] == 0


def test_recorded_watchlist_findings_are_compared_with_the_records() -> None:
    far = {"comparable": True, "within_radius": 0, "radius_m": 5000.0}
    comparison = {"Ulex europaeus": far, "Clematis vitalba": far}
    corrected = {"kind": "correction", "species": "Clematis vitalba", "effort_seconds": 5}
    added = {"kind": "addition", "species": "Ulex europaeus", "effort_seconds": 5}
    photos = [
        photo("a", "v1", review_status="rejected", reference_comparison=comparison)
        | {"findings": [corrected]},
        photo("b", "v2", review_status="confirmed", reference_comparison=comparison)
        | {"findings": [added]},
    ]
    novel = measure(outcomes(export(photos, references=SNAPSHOT)), "novel_or_earlier_evidence")
    assert novel["value"] == {"photos": 2, "site_visits": 2, "ungrouped_photos": 0}
    assert novel["denominator"]["photos"] == 2


def test_novelty_with_a_snapshot_but_no_findings_is_not_yet_measurable() -> None:
    novel = measure(
        outcomes(export([photo("a", "a")], references=SNAPSHOT)), "novel_or_earlier_evidence"
    )
    assert novel["status"] == NOT_YET
    assert "no confirmed or recorded watchlist finding" in novel["reason"]


def test_rejected_and_inconclusive_reviews_are_reported_with_their_time() -> None:
    photos = [
        photo("a", "v1", review_status="rejected"),
        photo("b", "v2", review_status="uncertain", scores={"margin": -0.1}),
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
    assert alarms["evidence"]["rejected"]["site_visits"] == 1
    assert alarms["evidence"]["inconclusive"]["site_visits"] == 2
    assert alarms["evidence"]["rejected_or_inconclusive_with_positive_margin"]["photos"] == 2
    assert alarms["denominator"]["site_visits"] == 4
    assert alarms["evidence"]["minutes"] == 3.0
    assert alarms["evidence"]["untimed_decisions"] == 1
    assert "lower bound" in alarms["reason"]


def test_false_alarms_are_not_counted_until_proposed_leads_are_defined() -> None:
    photos = [photo("a", "a", review_status="rejected")]
    alarms = measure(
        outcomes(export(photos, {"a": [event("rejected", 60)]})), "false_alarm_workload"
    )
    assert alarms["status"] == PARTIAL
    assert alarms["value"] is None
    assert "#16" in alarms["reason"]


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


def test_audit_time_is_reviewer_effort_too() -> None:
    audits = [{"photo_id": "a", "events": [{"effort_seconds": 120}, {"effort_seconds": None}]}]
    report = outcomes(export([photo("a", "a")], audit_history=audits))
    effort = measure(report, "reviewer_effort_per_useful_finding")["evidence"]
    assert effort["audit_minutes"] == 2.0
    assert effort["untimed_audit_answers"] == 1


def test_minutes_are_unknown_rather_than_zero_when_nothing_was_timed() -> None:
    photos = [photo("a", "a", review_status="rejected")]
    report = outcomes(export(photos, {"a": [event("rejected", None)]}))
    assert measure(report, "false_alarm_workload")["evidence"]["minutes"] is None
    effort = measure(report, "reviewer_effort_per_useful_finding")["evidence"]
    assert effort["incidental_minutes"] is None
    assert effort["untimed_incidental_decisions"] == 1


def test_time_on_recorded_findings_is_reviewer_effort() -> None:
    added = {"kind": "addition", "species": "Ulex europaeus", "effort_seconds": 60}
    untimed = {"kind": "correction", "other_taxon": "Toetoe", "effort_seconds": None}
    photos = [photo("a", "a", review_status="rejected", findings=[added, untimed])]
    report = outcomes(export(photos, {"a": [event("rejected", 60)]}))
    effort = measure(report, "reviewer_effort_per_useful_finding")["evidence"]
    assert effort["incidental_minutes"] == 2.0
    assert effort["timed_incidental_decisions"] == 1
    assert effort["timed_incidental_findings"] == 1
    assert effort["untimed_incidental_findings"] == 1
    alarms = measure(report, "false_alarm_workload")
    assert alarms["evidence"]["minutes"] == 2.0
    assert alarms["evidence"]["untimed_decisions"] == 0
    assert alarms["evidence"]["untimed_findings"] == 1
    assert "1 recorded finding was not timed" in alarms["reason"]


def test_time_on_judgements_is_reviewer_effort() -> None:
    run = export([photo("a", "a", review_status="rejected")], {"a": [event("rejected", 60)]})
    run["review_history"][0]["judgements"] = [
        {"dimension": "novelty", "value": "new_in_photo", "effort_seconds": 30},
        {"dimension": "identity", "value": "disputed", "effort_seconds": None},
    ]
    report = outcomes(run)
    effort = measure(report, "reviewer_effort_per_useful_finding")["evidence"]
    assert effort["incidental_minutes"] == 1.5
    assert effort["timed_incidental_judgements"] == 1
    assert effort["untimed_incidental_judgements"] == 1
    alarms = measure(report, "false_alarm_workload")
    assert alarms["evidence"]["minutes"] == 1.5
    assert alarms["evidence"]["untimed_judgements"] == 1
    assert "1 judgement was not timed, so minutes are a lower bound" in alarms["reason"]


def test_reviewer_added_watchlist_plants_are_non_blind_missed_evidence() -> None:
    added = {"kind": "addition", "species": "Ulex europaeus", "effort_seconds": 5}
    other = {"kind": "addition", "other_taxon": "Toetoe", "effort_seconds": 5}
    photos = [photo("a", "v1", findings=[added]), photo("b", "v1", findings=[other])]
    missed = measure(outcomes(export(photos)), "missed_visible_targets")
    assert missed["status"] == NOT_YET
    assert missed["evidence"]["reviewer_added_watchlist_plants_not_blind"] == {
        "photos": 1,
        "site_visits": 1,
        "ungrouped_photos": 0,
    }


def referred(
    reason: str, at: str, closed: tuple[str, str] | None = None, seconds: float | None = 60
) -> dict[str, Any]:
    """A referral opened at `at`, closed by an untimed (action, time) event when given."""
    events = []
    if closed:
        action, when = closed
        events = [
            {"action": action, "actor": "Dr Wiri", "created_at": when, "effort_seconds": None}
        ]
    status = closed[0] if closed else "open"
    return {"reason": reason, "status": status, "created_at": at, "referrer": "Ana"} | {
        "effort_seconds": seconds,
        "events": events,
    }


def test_follow_up_counts_specialist_referrals_and_answer_turnaround() -> None:
    run = export([photo("a", "a"), photo("b", "b")])
    day = "2026-11-0{}T{:02d}:00:00+00:00".format
    run["review_history"][0]["referrals"] = [
        referred("lookalike", day(1, 0), ("answered", day(1, 6))),
        referred("lookalike", day(2, 0), ("answered", day(3, 0))),
        referred("poor_view", day(2, 0), ("withdrawn", day(2, 1))),
    ]
    run["review_history"][1]["referrals"] = [referred("cultivated_or_wild", day(4, 0))]
    follow_up = measure(outcomes(run), "follow_up_usefulness")
    assert follow_up["status"] == PARTIAL
    assert follow_up["value"] is None, "a referral is not a useful lead by itself"
    referrals = follow_up["evidence"]["referrals"]
    assert (referrals["referred"], referrals["open"]) == (4, 1)
    assert (referrals["answered"], referrals["withdrawn"]) == (2, 1)
    assert referrals["by_reason"] == {"lookalike": 2, "poor_view": 1, "cultivated_or_wild": 1}
    assert referrals["answer_turnaround_hours"] == {"median": 15.0, "longest": 24.0}
    assert follow_up["evidence"]["photos_with_open_referrals"]["photos"] == 1
    assert "#27" in follow_up["reason"]


def test_turnaround_is_unknown_until_a_referral_is_answered() -> None:
    run = export([photo("a", "a")])
    run["review_history"][0]["referrals"] = [referred("other", "2026-11-01T00:00:00+00:00")]
    referrals = measure(outcomes(run), "follow_up_usefulness")["evidence"]["referrals"]
    assert referrals["answer_turnaround_hours"] is None


def test_time_on_referrals_is_reviewer_effort() -> None:
    run = export([photo("a", "a", review_status="rejected")], {"a": [event("rejected", 60)]})
    run["review_history"][0]["referrals"] = [
        referred("lookalike", "2026-11-01T00:00:00Z", ("answered", "2026-11-02T00:00:00Z"), 30)
    ]
    report = outcomes(run)
    effort = measure(report, "reviewer_effort_per_useful_finding")["evidence"]
    assert effort["incidental_minutes"] == 1.5
    assert effort["timed_incidental_referral_actions"] == 1
    assert effort["untimed_incidental_referral_actions"] == 1
    alarms = measure(report, "false_alarm_workload")
    assert alarms["evidence"]["untimed_referral_actions"] == 1
    assert "1 referral action was not timed" in alarms["reason"]
