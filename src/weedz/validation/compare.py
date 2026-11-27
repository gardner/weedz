"""Compare saved proportions with independent Newcombe hybrid Wilson intervals."""

from collections import Counter
from dataclasses import dataclass
from typing import Literal

from weedz.validation.metrics import Rate, direction, is_gated, newcombe
from weedz.validation.scorecard import Scorecard

MetricKey = tuple[str, str, str]
Verdict = Literal["better", "worse", "no clear change", "changed", "new", "removed", "unmeasured"]
ORDER: tuple[Verdict, ...] = (
    "worse",
    "removed",
    "unmeasured",
    "changed",
    "no clear change",
    "new",
    "better",
)


@dataclass(frozen=True)
class Difference:
    value: float
    low: float
    high: float


@dataclass(frozen=True)
class MetricComparison:
    key: MetricKey
    baseline: Rate | None
    rerun: Rate | None
    verdict: Verdict
    difference: Difference | None = None

    @property
    def gated(self) -> bool:
        return any(is_gated(metric) for metric in (self.baseline, self.rerun) if metric is not None)


@dataclass(frozen=True)
class Comparison:
    rows: tuple[MetricComparison, ...]
    changes: dict[str, tuple[str, ...]]

    @property
    def exit_code(self) -> int:
        return int(any(row.gated and row.verdict == "worse" for row in self.rows))

    def markdown(self, *, limit: int | None = None) -> str:
        counts = Counter(row.verdict for row in self.rows)
        summary = ", ".join(f"{counts[verdict]} {verdict}" for verdict in ORDER if counts[verdict])
        lines = [
            f"{len(self.rows)} metrics: {summary or 'none'}.",
            "",
            "95% Newcombe intervals for rerun − baseline (percentage points). "
            "Gated regressions are marked; exit code 1 if any get worse.",
            "",
            "Runs on the same images are paired; this independent-proportions interval "
            "is conservative for this guard. Unknown directions are reported as changed, "
            "without a better/worse verdict.",
            "",
        ]
        for check, changes in self.changes.items():
            lines.extend([f"**{check}: not like-for-like:** {'; '.join(changes)}.", ""])
        lines.extend(
            [
                "| Check | Metric | Stratum | Baseline | Rerun | Δ (95% CI, pp) | Verdict |",
                "| --- | --- | --- | --- | --- | --- | --- |",
            ]
        )
        for row in self.rows[:limit]:
            verdict = row.verdict + (" (gated)" if row.gated and row.verdict == "worse" else "")
            lines.append(
                f"| {' | '.join(row.key)} | {_measure(row.baseline)} | {_measure(row.rerun)} "
                f"| {_interval(row.difference)} | {verdict} |"
            )
        if limit is not None and len(self.rows) > limit:
            lines.extend(
                ["", f"Showing {limit} of {len(self.rows)} metrics; use --markdown for all."]
            )
        return "\n".join(lines) + "\n"


def _index(card: Scorecard) -> dict[MetricKey, Rate]:
    # Also validate receipts loaded directly, rather than built with collect().
    Scorecard.collect(card.results)
    metrics: dict[MetricKey, Rate] = {}
    for result in card.results:
        for metric in result.metrics:
            key = result.check, metric.name, metric.stratum
            if key in metrics:
                raise ValueError(f"Each metric may appear once per check and stratum: {key}")
            metrics[key] = metric
    return metrics


def _changes(baseline: Scorecard, rerun: Scorecard) -> dict[str, tuple[str, ...]]:
    old = {result.check: result for result in baseline.results}
    new = {result.check: result for result in rerun.results}
    changes: dict[str, tuple[str, ...]] = {}
    for check in sorted(old.keys() & new.keys()):
        before, after = old[check], new[check]
        flags = []
        if before.inputs != after.inputs:
            paths = sorted(
                path
                for path in before.inputs.keys() | after.inputs.keys()
                if before.inputs.get(path) != after.inputs.get(path)
            )
            flags.append(f"inputs changed ({', '.join(paths)})")
        if before.split != after.split:
            flags.append(f"split changed ({before.split} → {after.split})")
        if before.dataset != after.dataset:
            flags.append(f"dataset changed ({before.dataset} → {after.dataset})")
        if flags:
            changes[check] = tuple(flags)
    return changes


def _direction(baseline: Rate, rerun: Rate) -> bool | None:
    # Preserve the baseline's gate/direction even if the rerun drops its gate.
    previous = direction(baseline)
    return previous if previous is not None else direction(rerun)


def _verdict(difference: Difference, higher: bool | None) -> Verdict:
    if higher is None:
        return "changed"
    if difference.low <= 0 <= difference.high:
        return "no clear change"
    return "better" if (difference.low > 0) == higher else "worse"


def _compare(key: MetricKey, baseline: Rate | None, rerun: Rate | None) -> MetricComparison:
    if baseline is None:
        return MetricComparison(key, baseline, rerun, "new")
    if rerun is None:
        return MetricComparison(key, baseline, rerun, "removed")
    if baseline.total == 0 or rerun.total == 0 or baseline.value is None or rerun.value is None:
        return MetricComparison(key, baseline, rerun, "unmeasured")
    low, high = newcombe(rerun.successes, rerun.total, baseline.successes, baseline.total)
    delta = rerun.successes / rerun.total - baseline.successes / baseline.total
    difference = Difference(delta, low, high)
    return MetricComparison(
        key, baseline, rerun, _verdict(difference, _direction(baseline, rerun)), difference
    )


def _sort_key(row: MetricComparison) -> tuple[int, float, MetricKey]:
    degradation = 0.0
    if row.verdict == "worse" and row.difference and row.baseline and row.rerun:
        degradation = row.difference.value * (1 if _direction(row.baseline, row.rerun) else -1)
    return ORDER.index(row.verdict), degradation, row.key


def compare_scorecards(baseline: Scorecard, rerun: Scorecard) -> Comparison:
    before, after = _index(baseline), _index(rerun)
    rows = [_compare(key, before.get(key), after.get(key)) for key in before.keys() | after.keys()]
    return Comparison(tuple(sorted(rows, key=_sort_key)), _changes(baseline, rerun))


def _measure(metric: Rate | None) -> str:
    if metric is None:
        return "—"
    if metric.value is None:
        return "unmeasured"
    return f"{metric.value:.1%} ({metric.successes}/{metric.total})"


def _interval(difference: Difference | None) -> str:
    if difference is None:
        return "—"
    return (
        f"{difference.value * 100:+.1f} "
        f"({difference.low * 100:+.1f} to {difference.high * 100:+.1f})"
    )
