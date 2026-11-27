"""Stage summaries count gates, leaving the complete metric table available below."""

from weedz.validation.metrics import Rate, rate
from weedz.validation.scorecard import CheckResult, Scorecard


def _result(name: str, stage: str, metrics: list[Rate]) -> CheckResult:
    return CheckResult(
        check=name, stage=stage, dataset="fixture", split="held-out", metrics=metrics
    )


def test_scorecard_starts_with_per_stage_gate_counts_and_headline_gates():
    card = Scorecard.collect(
        [
            _result(
                "screen",
                "plant-presence",
                [
                    rate("recall", 990, 1000, target=0.95),
                    rate("recall", 1, 10, target=0.95, stratum="small"),
                    rate("false_alarm", 0, 0, ceiling=0.05),
                    rate("diagnostic", 1, 10),
                ],
            ),
            _result("screen-2", "plant-presence", [rate("recall", 8, 10)]),
            _result("boxes", "region-proposals", [rate("recall", 1, 10, target=0.8)]),
        ]
    )
    markdown = card.markdown()
    assert "| Stage | Checks | Gated passing | Gated failing | Gated unmeasured |" in markdown
    assert "| plant-presence | 2 | 1 | 1 | 1 |" in markdown
    assert "| region-proposals | 1 | 0 | 1 | 0 |" in markdown
    headline, full = markdown.split("## Full results", maxsplit=1)
    assert "99.0% (98.2–99.5%)" in headline
    assert "unmeasured" in headline
    assert "| screen | recall |" in headline
    assert "| screen | false_alarm |" in headline
    assert "diagnostic" not in headline and "small" not in headline
    assert "diagnostic" in full and "small" in full
    assert "| plant-presence | screen | fixture | held-out | recall | all | 990/1000 |" in full


def test_empty_scorecard_and_stages_without_gates_still_render():
    assert "## Full results" in Scorecard.collect([]).markdown()
    markdown = Scorecard.collect([_result("a", "stage", [rate("recall", 9, 10)])]).markdown()
    assert "| stage | 1 | 0 | 0 | 0 |" in markdown
