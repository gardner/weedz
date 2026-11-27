"""Shared source verification and image-level scoring for agricultural checks."""

import hashlib
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass, field
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

import numpy as np
from numpy.typing import NDArray

from weedz.discovery.inference import file_sha256
from weedz.validation.cocostuff_data import atomic_file
from weedz.validation.metrics import Rate, rate
from weedz.validation.registry import RunContext

type BoolMask = NDArray[np.bool_]
type Configuration = dict[str, str | int | float | bool]
LIBRARIES = (
    "torch",
    "torchvision",
    "numpy",
    "pillow",
    "scipy",
    "pydantic",
    "sam3",
    "transformers",
    "timm",
    "safetensors",
)


def installed(name: str) -> str:
    try:
        return version(name)
    except PackageNotFoundError:
        return "not installed"


def configuration(context: RunContext) -> Configuration:
    return {
        **{f"{name}_version": installed(name) for name in LIBRARIES},
        "device": context.device,
        "operating_points": "Frozen before this port; no threshold or budget tuning",
        "image_coverage_threshold": 0.5,
        "image_limit": context.limit if context.limit is not None else "none",
    }


def materialize(root: Path, relative: Path, raw: bytes, inputs: dict[str, str]) -> Path:
    """Bind each extracted image/label to bytes read from a verified publisher archive."""
    path = root / relative
    expected = hashlib.sha256(raw).hexdigest()
    if not path.is_file() or file_sha256(path) != expected:
        with atomic_file(path) as stream:
            stream.write(raw)
    inputs[relative.as_posix()] = expected
    return path


def select[T](items: Sequence[T], limit: int | None) -> list[T]:
    if limit is not None and limit < 1:
        raise ValueError("The image limit must be positive")
    return list(items if limit is None else items[:limit])


@dataclass
class Tallies:
    counts: dict[tuple[str, str], list[int]] = field(
        default_factory=lambda: defaultdict(lambda: [0, 0])
    )
    fractions: dict[str, list[float]] = field(default_factory=lambda: defaultdict(list))

    def add(self, name: str, hit: bool, strata: Sequence[str] = ("all",)) -> None:
        for stratum in set(strata):
            count = self.counts[name, stratum]
            count[0] += int(hit)
            count[1] += 1

    def metrics(self) -> list[Rate]:
        return [
            rate(name, hits, total, stratum=stratum)
            for (name, stratum), (hits, total) in sorted(self.counts.items())
        ]

    def means(self) -> Configuration:
        return {f"mean_{key}": sum(values) / len(values) for key, values in self.fractions.items()}


def image_coverage(
    tally: Tallies, truth: BoolMask, prediction: BoolMask, stratum: str = "all"
) -> None:
    """One trial per assessed positive image, never one independent trial per pixel."""
    if truth.shape != prediction.shape or truth.ndim != 2:
        raise ValueError("Coverage masks must share a two-dimensional grid")
    total = int(truth.sum())
    if total:
        share = int((truth & prediction).sum()) / total
        tally.add("foreground_half_covered", share >= 0.5, (stratum,))
        tally.add("foreground_90pct_covered", share >= 0.9, (stratum,))
        tally.fractions[f"coverage_{stratum}"].append(share)


def mask_union(masks: Sequence[BoolMask], shape: tuple[int, int]) -> BoolMask:
    result = np.zeros(shape, dtype=np.bool_)
    for mask in masks:
        if mask.shape != shape:
            raise ValueError("Proposal mask differs from source geometry")
        result |= mask
    return result
