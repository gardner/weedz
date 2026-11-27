"""Rates with Wilson intervals, and the binary outcomes most checks reduce to."""

import math
from collections import defaultdict
from collections.abc import Iterable

from pydantic import BaseModel, ConfigDict, Field

Z_95 = 1.959963984540054


class Rate(BaseModel):
    """A measured proportion. A target or ceiling passes only if the whole interval clears it."""

    model_config = ConfigDict(frozen=True)

    name: str = Field(min_length=1)
    stratum: str = "all"
    successes: int = Field(ge=0)
    total: int = Field(ge=0)
    value: float | None
    low: float | None
    high: float | None
    target: float | None = None
    ceiling: float | None = None
    passed: bool | None = None
    higher_is_better: bool | None = None


def is_gated(metric: Rate) -> bool:
    return metric.target is not None or metric.ceiling is not None


def direction(metric: Rate) -> bool | None:
    """Resolve old receipts too; gates take precedence over names or explicit hints."""
    if metric.target is not None:
        return True
    if metric.ceiling is not None:
        return False
    if metric.higher_is_better is not None:
        return metric.higher_is_better
    name = metric.name.casefold()
    for terms, higher in (
        # Checked first: worst-species rates are false-alarm rates even with "top1" in them.
        (("false_alarm", "wrong_subject", "confusion", "worst_species", "nonvegetation"), False),
        (("recall", "recovery", "coverage", "covered", "identified", "top1", "top5", "_at5"), True),
    ):
        if any(term in name for term in terms):
            return higher
    return None


def wilson(successes: int, total: int, z: float = Z_95) -> tuple[float, float]:
    """The 95% Wilson score interval; sound for small counts and rates near 0 or 1."""
    p = successes / total
    denominator = 1 + z * z / total
    centre = (p + z * z / (2 * total)) / denominator
    half = z * math.sqrt(p * (1 - p) / total + z * z / (4 * total * total)) / denominator
    return max(0.0, centre - half), min(1.0, centre + half)


def development_floor(
    successes: int, total: int, held_out_total: int, higher_is_better: bool
) -> float | None:
    """Development Wilson bound widened by the expected held-out interval's distance.

    The pass test checks one side (a target needs the held-out *lower* bound to clear
    it), and Wilson intervals are lopsided near 0 and 1, so the widening uses the
    distance on that side, not the symmetric half-width.

    Only the held-out denominator enters the calculation. Empty development or
    held-out samples cannot establish a regression gate.
    """
    if not 0 <= successes <= total or held_out_total < 0:
        raise ValueError("Development gates require valid counts")
    if not total or not held_out_total:
        return None
    low, high = wilson(successes, total)
    expected_successes = round(successes / total * held_out_total)
    expected = expected_successes / held_out_total
    expected_low, expected_high = wilson(expected_successes, held_out_total)
    if higher_is_better:
        return max(0.0, low - (expected - expected_low))
    return min(1.0, high + (expected_high - expected))


def newcombe(
    successes: int, total: int, baseline_successes: int, baseline_total: int
) -> tuple[float, float]:
    """95% interval for first minus baseline: Newcombe (1998), method 10, no CC.

    Combines the two independent Wilson intervals (Stat Med 17:873–890).
    https://doi.org/10.1002/(SICI)1097-0258(19980430)17:8<873::AID-SIM779>3.0.CO;2-I
    """
    for hits, count in ((successes, total), (baseline_successes, baseline_total)):
        if count <= 0 or not 0 <= hits <= count:
            raise ValueError("Newcombe intervals require valid counts and positive totals")
    value, baseline = successes / total, baseline_successes / baseline_total
    low, high = wilson(successes, total)
    baseline_low, baseline_high = wilson(baseline_successes, baseline_total)
    delta = value - baseline
    return (
        delta - math.hypot(value - low, baseline_high - baseline),
        delta + math.hypot(high - value, baseline - baseline_low),
    )


def rate(
    name: str,
    successes: int,
    total: int,
    *,
    stratum: str = "all",
    target: float | None = None,
    ceiling: float | None = None,
    higher_is_better: bool | None = None,
) -> Rate:
    if not 0 <= successes <= total:
        raise ValueError(f"{name}: successes must be between zero and the total")
    if target is not None and ceiling is not None:
        raise ValueError(f"{name}: set a target or a ceiling, not both")
    low, high = wilson(successes, total) if total else (None, None)
    passed = None
    if target is not None and low is not None:
        passed = low >= target
    elif ceiling is not None and high is not None:
        passed = high <= ceiling
    measured = Rate(
        name=name,
        stratum=stratum,
        successes=successes,
        total=total,
        value=successes / total if total else None,
        low=low,
        high=high,
        target=target,
        ceiling=ceiling,
        passed=passed,
        higher_is_better=higher_is_better,
    )
    return measured.model_copy(update={"higher_is_better": direction(measured)})


class Outcome(BaseModel):
    """One labelled item: what the human label says and what the pipeline decided."""

    model_config = ConfigDict(frozen=True)

    item: str = Field(min_length=1)
    truth: bool
    predicted: bool
    stratum: str | None = None


def binary_metrics(
    outcomes: Iterable[Outcome],
    *,
    target_recall: float | None = None,
    false_alarm_ceiling: float | None = None,
) -> list[Rate]:
    """Recall on labelled positives and false-alarm rate on labelled negatives, per stratum."""
    counts: dict[tuple[str, bool], list[int]] = defaultdict(lambda: [0, 0])
    seen: set[str] = set()
    for outcome in outcomes:
        if outcome.item in seen:
            raise ValueError(f"Each item may be scored once: {outcome.item}")
        seen.add(outcome.item)
        for stratum in {"all", outcome.stratum or "all"}:
            tally = counts[stratum, outcome.truth]
            tally[0] += outcome.predicted
            tally[1] += 1
    metrics = []
    for (stratum, truth), (hits, total) in sorted(counts.items()):
        if truth:
            metrics.append(rate("recall", hits, total, stratum=stratum, target=target_recall))
        else:
            metrics.append(
                rate("false_alarm_rate", hits, total, stratum=stratum, ceiling=false_alarm_ceiling)
            )
    return metrics
