"""Independent reference intervals and comparisons of saved validation evidence."""

import pytest

from weedz.validation.compare import compare_scorecards
from weedz.validation.metrics import Rate, direction, newcombe, rate
from weedz.validation.scorecard import CheckResult, Scorecard


def _result(check: str, *metrics: Rate, **changes: object) -> CheckResult:
    result = CheckResult(
        check=check,
        stage="plant-presence",
        dataset="fixture",
        split="held-out",
        metrics=list(metrics),
        inputs={"labels.csv": "a" * 64, "model.pt": "b" * 64},
    )
    return result.model_copy(update=changes)


@pytest.mark.parametrize(
    "counts, expected",
    [
        ((56, 70, 48, 80), (0.0524, 0.3339)),
        ((9, 10, 3, 10), (0.1705, 0.8090)),
        ((0, 10, 0, 20), (-0.1611, 0.2775)),
    ],
)
def test_newcombe_matches_published_method_10_examples(
    counts: tuple[int, int, int, int], expected: tuple[float, float]
):
    # Newcombe (1998), Stat Med 17:873–890, Table II, method 10 (no CC).
    # https://doi.org/10.1002/(SICI)1097-0258(19980430)17:8<873::AID-SIM779>3.0.CO;2-I
    assert newcombe(*counts) == pytest.approx(expected, abs=0.00005)


def test_newcombe_reverses_sign_when_the_samples_are_swapped():
    low, high = newcombe(56, 70, 48, 80)
    assert newcombe(48, 80, 56, 70) == pytest.approx((-high, -low))


@pytest.mark.parametrize("counts", [(0, 0, 1, 2), (1, 2, 0, 0), (3, 2, 1, 2), (-1, 2, 1, 2)])
def test_newcombe_requires_valid_nonempty_samples(counts: tuple[int, int, int, int]):
    with pytest.raises(ValueError):
        newcombe(*counts)


@pytest.mark.parametrize(
    "metric, expected",
    [
        (rate("sam3_recall", 8, 10), True),
        (rate("region_recovery", 8, 10), True),
        (rate("mask_coverage", 8, 10), True),
        (rate("sam3_false_alarm_rate", 1, 10), False),
        (rate("pilot_wrong_subject", 1, 10), False),
        (rate("lookalike_confusion", 1, 10), False),
        (rate("unfamiliar", 8, 10), None),
        (rate("false_alarm", 8, 10, target=0.5), True),
        (rate("recall", 1, 10, ceiling=0.5), False),
        (rate("custom", 1, 10, higher_is_better=False), False),
    ],
)
def test_direction_is_inferred_for_new_rates(metric: Rate, expected: bool | None):
    assert metric.higher_is_better is expected
    assert direction(metric) is expected


def test_old_rates_load_without_a_direction_and_infer_it_at_comparison_time():
    data = rate("recall", 90, 100).model_dump(exclude={"higher_is_better"})
    old = Rate.model_validate(data)
    assert old.higher_is_better is None
    assert direction(old) is True
    comparison = compare_scorecards(
        Scorecard.collect([_result("screen", old)]),
        Scorecard.collect([_result("screen", rate("recall", 20, 100))]),
    )
    assert comparison.rows[0].verdict == "worse"


def test_matching_uses_check_name_and_stratum_and_keeps_missing_metrics():
    baseline = Scorecard.collect(
        [
            _result("a", rate("recall", 90, 100), rate("recall", 20, 100, stratum="small")),
            _result("removed-check", rate("recall", 4, 10)),
        ]
    )
    rerun = Scorecard.collect(
        [
            _result("a", rate("recall", 20, 100), rate("recovery", 4, 10)),
            _result("new-check", rate("recall", 8, 10)),
        ]
    )
    rows = {row.key: row for row in compare_scorecards(baseline, rerun).rows}
    assert rows["a", "recall", "all"].verdict == "worse"
    assert rows["a", "recall", "small"].verdict == "removed"
    assert rows["a", "recovery", "all"].verdict == "new"
    assert rows["removed-check", "recall", "all"].verdict == "removed"
    assert rows["new-check", "recall", "all"].verdict == "new"
    assert rows["a", "recovery", "all"].difference is None


@pytest.mark.parametrize(
    "empty_baseline, empty_rerun", [(True, False), (False, True), (True, True)]
)
def test_zero_denominators_are_unmeasured(empty_baseline: bool, empty_rerun: bool):
    baseline = rate("recall", 0, 0) if empty_baseline else rate("recall", 8, 10)
    rerun = rate("recall", 0, 0) if empty_rerun else rate("recall", 8, 10)
    comparison = compare_scorecards(
        Scorecard.collect([_result("a", baseline)]), Scorecard.collect([_result("a", rerun)])
    )
    assert comparison.rows[0].verdict == "unmeasured"
    assert comparison.rows[0].difference is None
    assert comparison.exit_code == 0


@pytest.mark.parametrize(
    "name, old_hits, new_hits, verdict",
    [
        ("recall", 20, 90, "better"),
        ("recall", 90, 20, "worse"),
        ("false_alarm_rate", 90, 20, "better"),
        ("false_alarm_rate", 20, 90, "worse"),
        ("recall", 90, 91, "no clear change"),
        ("recall", 90, 90, "no clear change"),
        ("unknown", 90, 20, "changed"),
        ("unknown", 90, 90, "no clear change"),
    ],
)
def test_verdicts_use_direction_and_the_difference_interval(
    name: str, old_hits: int, new_hits: int, verdict: str
):
    comparison = compare_scorecards(
        Scorecard.collect([_result("a", rate(name, old_hits, 100))]),
        Scorecard.collect([_result("a", rate(name, new_hits, 100))]),
    )
    row = comparison.rows[0]
    assert row.verdict == verdict
    assert row.difference is not None
    assert row.difference.value == pytest.approx((new_hits - old_hits) / 100)


@pytest.mark.parametrize(
    "changes, expected",
    [
        ({"inputs": {"labels.csv": "c" * 64, "model.pt": "b" * 64}}, "labels.csv"),
        ({"inputs": {"labels.csv": "a" * 64, "model.pt": "c" * 64}}, "model.pt"),
        ({"inputs": {}}, "inputs changed"),
        ({"split": "development"}, "split changed"),
        # A --limit smoke run keeps the same input hashes but scores fewer images.
        ({"configuration": {"smoke_limit": 50}}, "cohort changed (smoke_limit)"),
        ({"configuration": {"held_out_images": 50}}, "cohort changed (held_out_images)"),
    ],
)
def test_changed_evidence_is_flagged(changes: dict[str, object], expected: str):
    metric = rate("recall", 9, 10)
    comparison = compare_scorecards(
        Scorecard.collect([_result("a", metric)]),
        Scorecard.collect([_result("a", metric, **changes)]),
    )
    assert expected in " ".join(comparison.changes["a"])
    assert "not like-for-like" in comparison.markdown()
    assert expected in comparison.markdown()


@pytest.mark.parametrize(
    "configuration",
    [{"recorded_inference_seconds": 873.0}, {"sam3_threshold": 0.41}, {"torch_version": "2.16"}],
)
def test_measured_outputs_in_configuration_are_not_a_cohort_change(configuration: dict):
    # Timings, fitted thresholds and versions move on every legitimate rerun.
    metric = rate("recall", 9, 10)
    comparison = compare_scorecards(
        Scorecard.collect([_result("a", metric)]),
        Scorecard.collect([_result("a", metric, configuration=configuration)]),
    )
    assert comparison.changes == {}


def test_unchanged_evidence_has_no_change_flag():
    card = Scorecard.collect([_result("a", rate("recall", 9, 10))])
    assert compare_scorecards(card, card).changes == {}


def test_duplicate_metric_keys_are_rejected():
    card = Scorecard.collect([_result("a", rate("recall", 9, 10), rate("recall", 8, 10))])
    with pytest.raises(ValueError, match="once"):
        compare_scorecards(card, card)


def test_markdown_shows_worst_first_intervals_and_the_paired_data_limit():
    baseline = Scorecard.collect(
        [_result("a", rate("recall", 48, 80)), _result("z", rate("recall", 90, 100))]
    )
    rerun = Scorecard.collect(
        [_result("a", rate("recall", 56, 70)), _result("z", rate("recall", 20, 100))]
    )
    comparison = compare_scorecards(baseline, rerun)
    markdown = comparison.markdown()
    assert [row.key[0] for row in comparison.rows] == ["z", "a"]
    assert markdown.index("| z |") < markdown.index("| a |")
    assert "+20.0 (+5.2 to +33.4)" in markdown
    assert "percentage points" in markdown
    assert "Newcombe" in markdown and "95%" in markdown
    assert "paired" in markdown and "independent" in markdown
    assert "1 worse" in markdown and "1 better" in markdown


def test_small_rates_and_intervals_do_not_round_to_zero():
    metric = rate("wrong_subject", 15, 42680, ceiling=0.01)
    card = Scorecard.collect([_result("a", metric)])
    markdown = compare_scorecards(card, card).markdown()
    assert "0.035% (15/42680)" in markdown
    assert "(-0.0 to +0.0)" not in markdown


def test_a_small_increase_in_false_alarms_fails_the_guard():
    comparison = compare_scorecards(
        Scorecard.collect([_result("a", rate("false_alarm", 10, 100000, ceiling=0.01))]),
        Scorecard.collect([_result("a", rate("false_alarm", 100, 100000, ceiling=0.01))]),
    )
    assert comparison.rows[0].verdict == "worse"
    assert comparison.exit_code == 1


def test_the_largest_degradation_comes_first_in_either_direction():
    baseline = Scorecard.collect(
        [_result("a", rate("recall", 90, 100)), _result("z", rate("false_alarm", 10, 100))]
    )
    rerun = Scorecard.collect(
        [_result("a", rate("recall", 60, 100)), _result("z", rate("false_alarm", 80, 100))]
    )
    comparison = compare_scorecards(baseline, rerun)
    assert [row.key[0] for row in comparison.rows] == ["z", "a"]


def test_metrics_unmeasured_in_both_runs_come_last():
    baseline = Scorecard.collect(
        [_result("a", rate("recall", 0, 0)), _result("b", rate("recall", 50, 100))]
    )
    rerun = Scorecard.collect(
        [_result("a", rate("recall", 0, 0)), _result("b", rate("recall", 0, 0))]
    )
    rows = compare_scorecards(baseline, rerun).rows
    # Losing a measurement surfaces; never having one doesn't crowd the table.
    assert [row.key[0] for row in rows] == ["b", "a"]
