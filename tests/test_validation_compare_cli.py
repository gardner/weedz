"""The comparison guard reads saved JSON only and propagates a failing exit code."""

from pathlib import Path

import pytest

from weedz.validation.cli import main
from weedz.validation.metrics import rate
from weedz.validation.scorecard import CheckResult, Scorecard


def _result(hits: int, *, gated: bool = True) -> CheckResult:
    return CheckResult(
        check="screen",
        stage="plant-presence",
        dataset="fixture",
        split="held-out",
        metrics=[rate("recall", hits, 100, target=0.5 if gated else None)],
    )


@pytest.mark.parametrize(
    "hits, gated, expected", [(20, True, 1), (20, False, 0), (90, True, 0), (91, True, 0)]
)
def test_compare_cli_exit_code_and_markdown(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], hits: int, gated: bool, expected: int
):
    baseline = tmp_path / "baseline.json"
    Scorecard.collect([_result(90, gated=gated)]).write(baseline)
    rerun = tmp_path / "rerun.json"
    rerun.write_text(_result(hits, gated=gated).model_dump_json())
    markdown = tmp_path / "comparison.md"
    argv = ["compare", str(baseline), str(rerun), "--markdown", str(markdown)]
    if expected:
        with pytest.raises(SystemExit) as error:
            main(argv)
        assert error.value.code == expected
    else:
        main(argv)
    output = capsys.readouterr().out
    assert "screen" in output
    assert ("worse" if hits == 20 else "no clear change") in output
    assert "95%" in markdown.read_text()


def test_compare_accepts_a_scorecard_as_the_rerun(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
):
    card = tmp_path / "scorecard.json"
    Scorecard.collect([_result(90)]).write(card)
    main(["compare", str(card), str(card)])
    assert "no clear change" in capsys.readouterr().out


def test_baseline_gate_cannot_be_removed_to_hide_a_regression(tmp_path: Path):
    baseline = tmp_path / "baseline.json"
    Scorecard.collect([_result(90)]).write(baseline)
    rerun = tmp_path / "rerun.json"
    rerun.write_text(_result(20, gated=False).model_dump_json())
    with pytest.raises(SystemExit) as error:
        main(["compare", str(baseline), str(rerun)])
    assert error.value.code == 1


def test_compare_reports_removed_checks_when_given_individual_results(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
):
    baseline = tmp_path / "baseline.json"
    extra = _result(90).model_copy(update={"check": "other"})
    Scorecard.collect([_result(90), extra]).write(baseline)
    paths = [tmp_path / "screen.json", tmp_path / "new.json"]
    paths[0].write_text(_result(90).model_dump_json())
    paths[1].write_text(extra.model_copy(update={"check": "new"}).model_dump_json())
    main(["compare", str(baseline), *map(str, paths)])
    output = capsys.readouterr().out
    assert "removed" in output and "new" in output


def test_the_documented_glob_can_include_the_baseline_scorecard(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
):
    # `validate compare benchmarks/validation/scorecard.json benchmarks/validation/*.json`
    # passes the baseline scorecard among the results; it must not count twice.
    card = tmp_path / "scorecard.json"
    Scorecard.collect([_result(90)]).write(card)
    result = tmp_path / "screen.json"
    result.write_text(_result(90).model_dump_json())
    main(["compare", str(card), str(card), str(result)])
    assert "no clear change" in capsys.readouterr().out


def test_a_partial_rerun_reports_missing_checks_as_removed(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
):
    # The glob passes the baseline scorecard too; it must not fill in checks that weren't rerun.
    other = _result(90).model_copy(update={"check": "other"})
    card = tmp_path / "scorecard.json"
    Scorecard.collect([_result(90), other]).write(card)
    result = tmp_path / "screen.json"
    result.write_text(_result(90).model_dump_json())
    main(["compare", str(card), str(card), str(result)])
    output = capsys.readouterr().out
    assert "removed" in output


def test_two_result_files_for_one_check_are_rejected(tmp_path: Path):
    card = tmp_path / "scorecard.json"
    Scorecard.collect([_result(90)]).write(card)
    first, second = tmp_path / "a.json", tmp_path / "b.json"
    first.write_text(_result(90).model_dump_json())
    second.write_text(_result(20).model_dump_json())
    with pytest.raises(ValueError, match="screen"):
        main(["compare", str(card), str(first), str(second)])
