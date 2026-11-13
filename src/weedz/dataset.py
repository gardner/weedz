"""The upstream crop dataset: point observations, never segmentation masks."""

import csv
import math
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Literal

REPOSITORY = "mpg-ranch/leafy_spurge"
REVISION = "ede1689fa8d424bcaea2c02157e791d97e4eba04"
LICENSE = "CC-BY-4.0"
ATTRIBUTION = "Doherty et al., Leafy Spurge Dataset, https://doi.org/10.57967/hf/2508"
Split = Literal["train", "test"]


@dataclass(frozen=True)
class Observation:
    sample_id: int
    image_path: Path
    source_split: Split
    label: int
    longitude: float
    latitude: float
    easting: float
    northing: float
    cluster: int


def safe_path(root: Path, relative: str) -> Path:
    path = PurePosixPath(relative)
    if path.is_absolute() or ".." in path.parts or "\\" in relative:
        raise ValueError(f"Unsafe dataset path: {relative}")
    resolved = (root / path).resolve()
    if not resolved.is_relative_to(root.resolve()):
        raise ValueError(f"Dataset path escapes its directory: {relative}")
    return resolved


def _coordinate(row: dict[str, str], field: str, limit: float = math.inf) -> float:
    value = float(row[field])
    if not math.isfinite(value) or abs(value) > limit:
        raise ValueError(f"Invalid {field}: {row[field]}")
    return value


def _observation(row: dict[str, str], directory: Path, split: Split) -> Observation:
    if row["label"] not in {"present", "absent"}:
        raise ValueError(f"Unknown label: {row['label']}")
    image = safe_path(directory, row["file_name"])
    if not image.is_file():
        raise ValueError(f"Missing image: {image}")
    return Observation(
        sample_id=int(row["idx"]),
        image_path=image,
        source_split=split,
        label=int(row["label"] == "present"),
        longitude=_coordinate(row, "longitude", 180),
        latitude=_coordinate(row, "latitude", 90),
        easting=_coordinate(row, "easting"),
        northing=_coordinate(row, "northing"),
        cluster=int(row["cluster"]),
    )


def read_observations(root: Path) -> list[Observation]:
    observations: list[Observation] = []
    for split in ("train", "test"):
        directory = root / "data" / "crop" / split
        with (directory / "metadata.csv").open(newline="", encoding="utf-8") as handle:
            for number, row in enumerate(csv.DictReader(handle), start=2):
                try:
                    observations.append(_observation(row, directory, split))
                except (KeyError, TypeError, ValueError) as error:
                    raise ValueError(f"{split}/metadata.csv:{number}: {error}") from error
    ids = [row.sample_id for row in observations]
    paths = [row.image_path for row in observations]
    if len(set(ids)) != len(ids) or len(set(paths)) != len(paths):
        raise ValueError("Duplicate sample IDs or image paths in dataset")
    return observations
