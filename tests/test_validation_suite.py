"""The validation suite: rates with intervals, binary outcomes, scorecards and the CLI."""

import json
from pathlib import Path

import pytest

from weedz.validation.metrics import Outcome, binary_metrics, rate
from weedz.validation.registry import REGISTRY, Check, RunContext, register
from weedz.validation.scorecard import CheckResult, Scorecard


def test_a_rate_carries_a_wilson_interval():
    measured = rate("recall", 18, 24)
    assert measured.value == pytest.approx(0.75)
    assert measured.low == pytest.approx(0.5507, abs=1e-3)
    assert measured.high == pytest.approx(0.8800, abs=1e-3)


def test_an_empty_rate_is_unmeasured_rather_than_zero():
    measured = rate("recall", 0, 0)
    assert measured.value is None and measured.low is None and measured.high is None
    assert measured.passed is None


def test_a_target_passes_only_when_the_whole_interval_clears_it():
    assert rate("recall", 990, 1000, target=0.95).passed is True
    assert rate("recall", 23, 24, target=0.95).passed is False


def test_a_ceiling_bounds_rates_that_should_stay_low():
    assert rate("false_alarm_rate", 1, 1000, ceiling=0.05).passed is True
    assert rate("false_alarm_rate", 1, 10, ceiling=0.05).passed is False


def test_rates_reject_impossible_counts():
    with pytest.raises(ValueError):
        rate("recall", 5, 4)
    with pytest.raises(ValueError):
        rate("recall", 1, 2, target=0.9, ceiling=0.1)


def test_binary_outcomes_give_recall_and_false_alarms_per_stratum():
    outcomes = [
        Outcome(item="a", truth=True, predicted=True, stratum="small"),
        Outcome(item="b", truth=True, predicted=False, stratum="small"),
        Outcome(item="c", truth=True, predicted=True, stratum="large"),
        Outcome(item="d", truth=False, predicted=True),
        Outcome(item="e", truth=False, predicted=False),
    ]
    metrics = {(m.name, m.stratum): m for m in binary_metrics(outcomes, target_recall=0.95)}
    assert (metrics["recall", "all"].successes, metrics["recall", "all"].total) == (2, 3)
    assert (metrics["recall", "small"].successes, metrics["recall", "small"].total) == (1, 2)
    assert metrics["recall", "large"].total == 1
    assert (metrics["false_alarm_rate", "all"].successes,) == (1,)
    assert metrics["false_alarm_rate", "all"].total == 2
    assert metrics["recall", "all"].target == 0.95


def test_binary_outcomes_reject_repeated_items():
    repeated = [Outcome(item="a", truth=True, predicted=True)] * 2
    with pytest.raises(ValueError, match="once"):
        binary_metrics(repeated)


def _result(name: str = "demo") -> CheckResult:
    return CheckResult(
        check=name,
        stage="plant-presence",
        dataset="demo-set",
        split="validation",
        metrics=[rate("recall", 9, 10, target=0.8)],
        limits=["Fixture only"],
        inputs={"labels.csv": "0" * 64},
    )


def test_a_scorecard_renders_one_row_per_metric_and_round_trips(tmp_path: Path):
    card = Scorecard.collect([_result("b"), _result("a")])
    assert [r.check for r in card.results] == ["a", "b"]
    path = tmp_path / "card.json"
    card.write(path)
    assert Scorecard.read(path) == card
    table = card.markdown()
    assert "| plant-presence | a | demo-set | validation | recall | all | 9/10 |" in table
    assert "90.0% (59.6–98.2%)" in table


def test_a_scorecard_refuses_two_results_for_one_check():
    with pytest.raises(ValueError, match="once"):
        Scorecard.collect([_result(), _result()])


def test_checks_register_once_and_run_with_their_context(tmp_path: Path):
    def run(context: RunContext) -> CheckResult:
        assert context.limit == 3
        return _result("fixture-check")

    register(Check(name="fixture-check", stage="plant-presence", dataset="demo", run=run))
    try:
        with pytest.raises(ValueError, match="already"):
            register(Check(name="fixture-check", stage="x", dataset="y", run=run))
        context = RunContext(data_root=tmp_path, cache_dir=tmp_path, device="cpu", limit=3)
        assert REGISTRY["fixture-check"].run(context).check == "fixture-check"
    finally:
        REGISTRY.pop("fixture-check")


def test_the_cli_runs_a_check_then_builds_the_scorecard(tmp_path: Path):
    from weedz.validation.cli import main

    register(
        Check(
            name="cli-check",
            stage="plant-presence",
            dataset="demo",
            run=lambda _: _result("cli-check"),
        )
    )
    try:
        results = tmp_path / "results"
        main(["run", "cli-check", "--data-root", str(tmp_path), "--output", str(results)])
        saved = results / "cli-check.json"
        assert json.loads(saved.read_text())["check"] == "cli-check"
        card = tmp_path / "scorecard.json"
        table = tmp_path / "scorecard.md"
        main(["scorecard", str(saved), "--output", str(card), "--markdown", str(table)])
        assert Scorecard.read(card).results[0].check == "cli-check"
        assert "cli-check" in table.read_text()
    finally:
        REGISTRY.pop("cli-check")


def test_rebuilding_the_scorecard_skips_its_own_previous_output(tmp_path: Path):
    # The documented command globs benchmarks/validation/*.json, which includes
    # the scorecard.json written by the previous run.
    from weedz.validation.cli import main

    saved = tmp_path / "cli-check.json"
    saved.write_text(_result("cli-check").model_dump_json())
    card = tmp_path / "scorecard.json"
    main(["scorecard", str(saved), "--output", str(card)])
    main(["scorecard", str(saved), str(card), "--output", str(card)])
    assert [result.check for result in Scorecard.read(card).results] == ["cli-check"]
