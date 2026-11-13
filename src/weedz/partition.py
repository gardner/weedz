"""Deterministic survey-group holdouts with a distance guard for tiny crops."""

import math
from dataclasses import dataclass

from weedz.dataset import Observation


@dataclass(frozen=True)
class Partitions:
    fit: list[Observation]
    validation: list[Observation]
    test: list[Observation]
    excluded: list[Observation]

    def items(self) -> dict[str, list[Observation]]:
        return {
            "fit": self.fit,
            "validation": self.validation,
            "test": self.test,
            "excluded": self.excluded,
        }


def _near(row: Observation, holdout: list[Observation], distance: float) -> bool:
    return any(
        (row.easting - other.easting) ** 2 + (row.northing - other.northing) ** 2 <= distance**2
        for other in holdout
    )


def partition_observations(observations: list[Observation], *, buffer_m: float = 2.0) -> Partitions:
    if buffer_m < 0 or not math.isfinite(buffer_m):
        raise ValueError("Spatial buffer must be finite and nonnegative")
    train = [row for row in observations if row.source_split == "train"]
    test = [row for row in observations if row.source_split == "test"]
    train_clusters = {row.cluster for row in train}
    if train_clusters & {row.cluster for row in test}:
        raise ValueError("Published train and test partitions share a survey cluster")
    if len(train_clusters) < 2 or not test:
        raise ValueError("Need at least two training clusters and a published test set")
    validation_cluster = max(train_clusters)
    validation = [
        row for row in train if row.cluster == validation_cluster and not _near(row, test, buffer_m)
    ]
    fit = [
        row
        for row in train
        if row.cluster != validation_cluster and not _near(row, validation + test, buffer_m)
    ]
    for name, rows in (("fit", fit), ("validation", validation)):
        if {row.label for row in rows} != {0, 1}:
            raise ValueError(f"{name} must contain both classes after spatial buffering")
    kept_ids = {row.sample_id for row in fit + validation + test}
    excluded = [row for row in observations if row.sample_id not in kept_ids]
    return Partitions(fit, validation, test, excluded)
