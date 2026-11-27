"""Compare saved proportions with independent Newcombe hybrid Wilson intervals."""

import math
from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal

from weedz.validation.metrics import Rate, direction, is_gated, newcombe
from weedz.validation.scorecard import Scorecard

MetricKey = tuple[str, str, str]
Verdict = Literal["better", "worse", "no clear change", "changed", "new", "removed", "unmeasured"]
COHORT_KEYS = frozenset({"held_out_images", "selected_images"})
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
            "Runs on the same images are paired, but results don't keep per-image outcomes, so "
            "this interval treats them as independent. That is usually wider than a paired "
            "interval, but not always: read a borderline verdict with care. "
            "A metric with no known direction is reported as changed when its interval "
            "excludes 0, without a better/worse verdict.",
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


def _is_cohort_key(key: str) -> bool:
    """Configuration keys that say which items were scored, not what the run measured.

    Configuration also holds measured outputs (timings, fitted thresholds, evidence
    fingerprints, versions) that move on every legitimate rerun.
    """
    return "limit" in key or "cohort" in key or key.startswith("scored_") or key in COHORT_KEYS


def _changed_keys(before: Mapping[str, object], after: Mapping[str, object]) -> list[str]:
    return sorted(key for key in before.keys() | after.keys() if before.get(key) != after.get(key))


def _changes(baseline: Scorecard, rerun: Scorecard) -> dict[str, tuple[str, ...]]:
    old = {result.check: result for result in baseline.results}
    new = {result.check: result for result in rerun.results}
    changes: dict[str, tuple[str, ...]] = {}
    for check in sorted(old.keys() & new.keys()):
        before, after = old[check], new[check]
        flags = []
        if keys := _changed_keys(before.inputs, after.inputs):
            flags.append(f"inputs changed ({', '.join(keys)})")
        if keys := [
            key
            for key in _changed_keys(before.configuration, after.configuration)
            if _is_cohort_key(key)
        ]:
            flags.append(f"cohort changed ({', '.join(keys)})")
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
    if difference.low <= 0 <= difference.high:
        return "no clear change"
    if higher is None:
        return "changed"
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
    never_measured = row.verdict == "unmeasured" and not (row.baseline and row.baseline.total)
    rank = len(ORDER) if never_measured else ORDER.index(row.verdict)
    return rank, degradation, row.key


def compare_scorecards(baseline: Scorecard, rerun: Scorecard) -> Comparison:
    before, after = _index(baseline), _index(rerun)
    rows = [_compare(key, before.get(key), after.get(key)) for key in before.keys() | after.keys()]
    return Comparison(tuple(sorted(rows, key=_sort_key)), _changes(baseline, rerun))


def _measure(metric: Rate | None) -> str:
    if metric is None:
        return "—"
    if metric.value is None:
        return "unmeasured"
    precision = _precision(metric.value)
    return f"{metric.value:.{precision}%} ({metric.successes}/{metric.total})"


def _interval(difference: Difference | None) -> str:
    if difference is None:
        return "—"
    precision = _precision(difference.value, difference.low, difference.high)
    return (
        f"{difference.value * 100:+.{precision}f} "
        f"({difference.low * 100:+.{precision}f} to {difference.high * 100:+.{precision}f})"
    )


def _precision(*values: float) -> int:
    """Keep at least two significant digits in small nonzero percentages."""
    nonzero = [abs(value * 100) for value in values if value != 0]
    return max(1, 1 - math.floor(math.log10(min(nonzero)))) if nonzero else 1
