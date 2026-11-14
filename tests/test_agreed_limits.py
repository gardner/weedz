"""Measured outcomes meet agreed limits only where both a limit and a value exist."""

from typing import Any

from test_outcomes import event, export, measure, photo

from weedz.discovery.agreed_limits import compare
from weedz.discovery.outcome_report import to_markdown
from weedz.discovery.outcomes import outcomes
from weedz.discovery.study import Limit, LimitTerms


def linked(**fields: Any) -> dict[str, Any]:
    return {
        "id": "study-1",
        "version": 3,
        "author": "Ana",
        "created_at": "2026-11-14T00:00:00+00:00",
        "definition": {"question": "Which sites would DOC visit?"} | fields,
    }


def reviewed_export(**extra: Any) -> dict[str, Any]:
    photos = [photo("a", "a", review_status="rejected"), photo("b", "b")]
    return export(
        photos,
        {"a": [event("rejected", 120)]},
        review_effort={"total_minutes": 2.0, **dict.fromkeys(UNMEASURED, 0)},
        **extra,
    )


UNMEASURED = [
    "unmeasured_decisions",
    "unmeasured_findings",
    "unmeasured_judgements",
    "unmeasured_referral_actions",
]


def test_without_a_study_no_verdict_is_given() -> None:
    report = outcomes(reviewed_export())
    assert report["study"] is None
    for item in report["measures"]:
        assert item["limit"]["verdict"] == "not agreed"
        assert item["limit"]["agreed"] is None


def test_a_limit_not_agreed_gives_no_verdict_even_with_a_measured_value() -> None:
    report = outcomes(reviewed_export(study=linked(limits={"coverage": {"value": 40}})))
    coverage = measure(report, "coverage")["limit"]
    assert (coverage["agreed"], coverage["measured"], coverage["verdict"]) == (40, 50.0, "met")
    assert coverage["direction"] == "at least"
    completeness = measure(report, "evidence_completeness")["limit"]
    assert completeness["verdict"] == "not agreed"
    assert completeness["measured"] == 100.0


def test_a_value_short_of_the_limit_is_not_met() -> None:
    incomplete = [photo("a", "a", review_status="rejected"), photo("b", "b", sha256="")]
    study = linked(limits={"evidence_completeness": {"value": 75}})
    report = outcomes(export(incomplete, study=study))
    result = measure(report, "evidence_completeness")["limit"]
    assert (result["measured"], result["verdict"]) == (50.0, "not met")


def test_coverage_short_of_its_limit_is_unsettled_while_photos_wait_for_review() -> None:
    """Coverage only grows as review goes on, so a shortfall is not yet a failure."""
    report = outcomes(reviewed_export(study=linked(limits={"coverage": {"value": 75}})))
    result = measure(report, "coverage")["limit"]
    assert result["verdict"] == "not comparable"
    assert "lower bound" in result["reason"]
    every = [photo("a", "a", review_status="rejected")]
    full = outcomes(export(every, study=linked(limits={"coverage": {"value": 75}})))
    assert measure(full, "coverage")["limit"]["verdict"] == "met"


def test_an_agreed_limit_on_an_unmeasurable_measure_is_not_comparable_with_a_reason() -> None:
    report = outcomes(
        reviewed_export(study=linked(limits={"useful_incidental_yield": {"value": 3}}))
    )
    result = measure(report, "useful_incidental_yield")["limit"]
    assert result["verdict"] == "not comparable"
    assert result["measured"] is None
    assert "#18" in result["reason"]


def test_a_lower_bound_decides_only_when_it_already_settles_the_limit() -> None:
    item = {"key": "x", "status": "partially measured", "reason": "untimed work"}
    at_most = LimitTerms("Effort", "at most", "minutes")
    assert compare(item, Limit(value=5), at_most, (6.0, True))["verdict"] == "not met"
    undecided = compare(item, Limit(value=5), at_most, (4.0, True))
    assert undecided["verdict"] == "not comparable"
    assert "lower bound" in undecided["reason"]
    at_least = LimitTerms("Yield", "at least", "site visits")
    assert compare(item, Limit(value=5), at_least, (6.0, True))["verdict"] == "met"
    assert compare(item, Limit(value=5), at_least, (4.0, True))["verdict"] == "not comparable"
    assert compare(item, Limit(value=5), at_least, (5.0, False))["verdict"] == "met"


def test_the_report_carries_the_study_its_open_decisions_and_budget_use() -> None:
    study = linked(review_budget={"hours": 1, "photos": 1})
    report = outcomes(reviewed_export(study=study))
    summary = report["study"]
    assert (summary["id"], summary["version"], summary["status"]) == ("study-1", 3, "provisional")
    assert "Partner" in summary["open_decisions"]
    assert summary["budget_use"]["hours"]["used"] == 0.03
    assert summary["budget_use"]["photos"] == {
        "budget": 1,
        "used": 1,
        "lower_bound": False,
        "state": "spent",
    }
    assert "agreed limit" in report["meaning"]


def test_markdown_shows_the_study_limits_and_verdicts() -> None:
    study = linked(limits={"coverage": {"value": 40, "note": "Half the queue"}})
    text = to_markdown(outcomes(reviewed_export(study=study, references=None)))
    assert "## Study" in text
    assert "study-1, version 3 (provisional)" in text
    assert "| Agreed limit | Verdict |" in text
    assert "at least 40 % of incidental photos reviewed" in text
    assert "| met (measured 50) |" in text
    assert "not agreed" in text
    plain = to_markdown(outcomes(reviewed_export()))
    assert "No study is linked to this run" in plain
