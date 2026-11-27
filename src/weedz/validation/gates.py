"""Apply development regression gates without changing pooled diagnostic rows."""

import hashlib
import json
from collections.abc import Callable, Iterable, Sequence

from weedz.validation.metrics import Rate, development_floor, direction, rate
from weedz.validation.splits import split_of

type Configuration = dict[str, str | int | float | bool]
RULE = "95% development Wilson bound widened by expected held-out Wilson half-width"


def cohort_sha256(items: Iterable[tuple[str, str]]) -> str:
    """Bind source IDs and scoring strata without depending on traversal order."""
    return hashlib.sha256(json.dumps(sorted(items)).encode()).hexdigest()


def prefixed(metrics: list[Rate], split: str) -> list[Rate]:
    return [
        row.model_copy(
            update={"stratum": split if row.stratum == "all" else f"{split}/{row.stratum}"}
        )
        for row in metrics
    ]


def hash_split_metrics[T](
    items: Sequence[T], score: Callable[[list[T]], list[Rate]], source_id: Callable[[T], str]
) -> list[Rate]:
    """Keep all existing rows, adding the frozen source-ID halves as strata."""
    metrics = score(list(items))
    for split in ("development", "held-out"):
        metrics.extend(
            prefixed(score([i for i in items if split_of(source_id(i)) == split]), split)
        )
    return metrics


def apply_development_gates(
    metrics: list[Rate],
    development: list[Rate],
    names: tuple[str, ...],
    configuration: Configuration,
    limits: list[str],
    *,
    development_stratum: str = "all",
    held_out_stratum: str = "all",
) -> list[Rate]:
    """Gate only explicit headlines; retain development counts and missing-data reasons."""
    configuration["gate_rule"] = RULE
    by_name = {row.name: row for row in development if row.stratum == development_stratum}
    existing = {(row.name, row.stratum) for row in metrics}
    metrics = [
        *metrics,
        *(
            rate(name, 0, 0, stratum=held_out_stratum)
            for name in names
            if (name, held_out_stratum) not in existing
        ),
    ]
    result = []
    for row in metrics:
        if row.name not in names or row.stratum != held_out_stratum:
            result.append(row)
            continue
        dev = by_name.get(row.name)
        successes, total = (dev.successes, dev.total) if dev else (0, 0)
        configuration[f"gate_development_{row.name}"] = f"{successes}/{total}"
        higher = direction(row)
        if higher is None:
            raise ValueError(f"Gate metric needs an explicit direction: {row.name}")
        bound = development_floor(successes, total, row.total, higher)
        if bound is None:
            limits.append(f"{row.name} ungated: no assessed development or held-out trials.")
        result.append(
            rate(
                row.name,
                row.successes,
                row.total,
                stratum=row.stratum,
                target=bound if higher else None,
                ceiling=None if higher else bound,
                higher_is_better=higher,
            )
        )
    return result
