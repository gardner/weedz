"""The Leafy Spurge baseline's split, frozen as a release.

It reproduces `partition.py`: the published test, the highest training survey cluster as
validation, and a 2 m buffer. The test has already been reported and inspected, so the
release records it as no longer fresh.
"""

from collections.abc import Mapping, Sequence
from pathlib import Path

from weedz.adapters import leafy_spurge_samples
from weedz.contract import Sample
from weedz.release import (
    ExplicitSplit,
    Release,
    ReleaseSpec,
    SplitName,
    build_release,
    write_release,
)

BASELINE_BUFFER_M = 2.0
PROTOCOL = (
    "Fit the colour/texture model on fit; choose the threshold meeting the target recall "
    "on validation; evaluate test once. The test was reported and inspected, so it is "
    "development data for any further tuning, not a fresh holdout."
)
Mismatches = dict[str, dict[str, list[str]]]


def leafy_spurge_spec(samples: list[Sample]) -> ReleaseSpec:
    """Assign whole survey clusters as the baseline does."""
    published: dict[str, set[str]] = {"train": set(), "test": set()}
    for sample in samples:
        published[sample.groups["source_split"]].add(sample.groups["survey_cluster"])
    train, test = published["train"], published["test"]
    if train & test:
        raise ValueError("Published train and test partitions share a survey cluster")
    if len(train) < 2 or not test:
        raise ValueError("Need at least two training clusters and a published test set")
    assignment: dict[str, SplitName] = {cluster: "test" for cluster in test}
    assignment |= {cluster: "fit" for cluster in train}
    assignment[max(train, key=int)] = "validation"
    return ReleaseSpec(
        name="leafy-spurge-baseline",
        task="point_classification",
        protocol=PROTOCOL,
        split=ExplicitSplit(group_key="survey_cluster", assignment=assignment),
        buffer_m=BASELINE_BUFFER_M,
        test_status="inspected",
    )


def partition_mismatches(release: Release, recorded: Mapping[str, Sequence[int]]) -> Mismatches:
    """Differences from a run's recorded partition IDs (`run.json` "partitions")."""
    mismatches: Mismatches = {}
    for name in ("fit", "validation", "test", "excluded"):
        ours = set(release.excluded) if name == "excluded" else set(release.splits[name].samples)
        theirs = {f"leafy-spurge:{sample_id}" for sample_id in recorded.get(name, [])}
        if ours != theirs:
            mismatches[name] = {
                "only_release": sorted(ours - theirs),
                "only_recorded": sorted(theirs - ours),
            }
    return mismatches


def write_leafy_spurge_release(
    data_dir: Path,
    output_dir: Path,
    *,
    recorded_at: str | None = None,
    expected: Mapping[str, Sequence[int]] | None = None,
) -> Release:
    """Write the baseline release, first checking it against `expected` partitions."""
    samples = leafy_spurge_samples(data_dir)
    spec = leafy_spurge_spec(samples)
    if expected is not None:
        release, _ = build_release(samples, spec, recorded_at=recorded_at or "unwritten")
        if mismatches := partition_mismatches(release, expected):
            summary = "; ".join(
                f"{name}: {len(sides['only_release'])} only in the release, "
                f"{len(sides['only_recorded'])} only recorded"
                for name, sides in mismatches.items()
            )
            raise ValueError(f"Release differs from the recorded partitions ({summary})")
    return write_release(output_dir, samples, spec, recorded_at=recorded_at)
