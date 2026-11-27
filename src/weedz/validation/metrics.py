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


def wilson(successes: int, total: int, z: float = Z_95) -> tuple[float, float]:
    """The 95% Wilson score interval; sound for small counts and rates near 0 or 1."""
    p = successes / total
    denominator = 1 + z * z / total
    centre = (p + z * z / (2 * total)) / denominator
    half = z * math.sqrt(p * (1 - p) / total + z * z / (4 * total * total)) / denominator
    return max(0.0, centre - half), min(1.0, centre + half)


def rate(
    name: str,
    successes: int,
    total: int,
    *,
    stratum: str = "all",
    target: float | None = None,
    ceiling: float | None = None,
) -> Rate:
    if not 0 <= successes <= total:
        raise ValueError(f"{name}: successes must be between zero and the total")
    if target is not None and ceiling is not None:
        raise ValueError(f"{name}: set a target or a ceiling, not both")
    if total == 0:
        return Rate(
            name=name,
            stratum=stratum,
            successes=0,
            total=0,
            value=None,
            low=None,
            high=None,
            target=target,
            ceiling=ceiling,
        )
    low, high = wilson(successes, total)
    passed = None
    if target is not None:
        passed = low >= target
    elif ceiling is not None:
        passed = high <= ceiling
    return Rate(
        name=name,
        stratum=stratum,
        successes=successes,
        total=total,
        value=successes / total,
        low=low,
        high=high,
        target=target,
        ceiling=ceiling,
        passed=passed,
    )


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
