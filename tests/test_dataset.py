from pathlib import Path

import pytest

from weedz.dataset import read_observations
from weedz.partition import partition_observations


def test_spatial_partitions_keep_clusters_and_published_test_separate(dataset_dir: Path) -> None:
    observations = read_observations(dataset_dir)
    partitions = partition_observations(observations, buffer_m=2)
    assert {row.cluster for row in partitions.fit} == {0, 1}
    assert {row.cluster for row in partitions.validation} == {2}
    assert {row.cluster for row in partitions.test} == {3}
    assert len(partitions.fit) + len(partitions.validation) + len(partitions.test) == 48


def test_buffer_removes_training_points_near_holdout(dataset_dir: Path) -> None:
    from dataclasses import replace

    observations = read_observations(dataset_dir)
    holdout = next(row for row in observations if row.cluster == 3)
    observations[0] = replace(
        observations[0], easting=holdout.easting + 1, northing=holdout.northing
    )
    partitions = partition_observations(observations, buffer_m=2)
    assert observations[0] in partitions.excluded
    assert observations[0] not in partitions.fit


@pytest.mark.parametrize("value", ["../escape.tif", "/absolute.tif", "present/../../escape.tif"])
def test_rejects_metadata_paths_outside_dataset(dataset_dir: Path, value: str) -> None:
    path = dataset_dir / "data/crop/train/metadata.csv"
    path.write_text(path.read_text().replace("absent/0_0.tif", value))
    with pytest.raises(ValueError, match="path"):
        read_observations(dataset_dir)


@pytest.mark.parametrize("field,value", [("label", "maybe"), ("latitude", "nan")])
def test_rejects_invalid_labels_and_coordinates(dataset_dir: Path, field: str, value: str) -> None:
    import csv

    path = dataset_dir / "data/crop/train/metadata.csv"
    with path.open() as handle:
        rows = list(csv.DictReader(handle))
    rows[0][field] = value
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    with pytest.raises(ValueError, match=field):
        read_observations(dataset_dir)


def test_rejects_clusters_shared_with_test(dataset_dir: Path) -> None:
    from dataclasses import replace

    rows = read_observations(dataset_dir)
    rows[-1] = replace(rows[-1], cluster=0)
    with pytest.raises(ValueError, match="cluster"):
        partition_observations(rows)
