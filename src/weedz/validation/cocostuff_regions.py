"""Mask proposal recovery on COCO-Stuff components and COCO plant instances."""

from collections import Counter
from collections.abc import Iterable, Sequence
from dataclasses import dataclass

import numpy as np
from scipy import ndimage

from weedz.region_evaluation.coverage import sparse_coverage
from weedz.region_evaluation.geometry import mask_overlap
from weedz.validation.cocostuff_data import SIZE_STRATA, BoolMask, Masks, vegetation_stratum
from weedz.validation.metrics import Rate, rate

PROPOSAL_LIMIT = 100
REGION_THRESHOLD = 0.5
BACKGROUND_THRESHOLD = 0.8
METRICS = (
    "half_covered_images",
    "component_iou_recall",
    "component_coverage_recall",
    "potted_plant_iou_recall",
    "potted_plant_coverage_recall",
    "nonvegetation_proposal_share",
)


@dataclass(frozen=True)
class RegionRecovery:
    pixels: int
    iou: bool
    coverage: bool


def _component_recovery(truth: Masks, proposals: Sequence[BoolMask]) -> Iterable[RegionRecovery]:
    # The aggregate component ID grid avoids scanning the full image once per tiny fragment.
    components = np.empty(truth.vegetation.shape, dtype=np.int32)
    ndimage.label(truth.vegetation, structure=np.ones((3, 3)), output=components)
    areas = np.bincount(components.ravel())[1:]
    if not areas.size:
        return ()
    best_iou = np.zeros(areas.size)
    best_coverage = np.zeros(areas.size)
    for proposal in proposals:
        assessed = proposal & ~truth.void
        intersection = np.bincount(components[assessed], minlength=areas.size + 1)[1:]
        proposed = int(np.count_nonzero(assessed))
        best_iou = np.maximum(best_iou, intersection / (areas + proposed - intersection))
        best_coverage = np.maximum(best_coverage, intersection / areas)
    return (
        RegionRecovery(int(area), bool(iou >= REGION_THRESHOLD), bool(coverage >= REGION_THRESHOLD))
        for area, iou, coverage in zip(areas, best_iou, best_coverage, strict=True)
    )


def _instance_recovery(
    truth: BoolMask, labelled: BoolMask, proposals: Sequence[BoolMask]
) -> RegionRecovery:
    assessed = labelled | truth
    pixels = int(np.count_nonzero(truth))
    overlaps = [mask_overlap(truth, proposal, assessed=assessed) for proposal in proposals]
    return RegionRecovery(
        pixels,
        any((overlap.iou or 0) >= REGION_THRESHOLD for overlap in overlaps),
        any(overlap.intersection_pixels >= REGION_THRESHOLD * pixels for overlap in overlaps),
    )


class ProposalCounts:
    def __init__(self) -> None:
        self.hits: Counter[tuple[str, str]] = Counter()
        self.totals: Counter[tuple[str, str]] = Counter()

    def add(self, name: str, stratum: str, hits: int, total: int) -> None:
        for key in {(name, stratum), (name, "all")}:
            self.hits[key] += hits
            self.totals[key] += total

    def metrics(self) -> list[Rate]:
        return [
            rate(name, self.hits[name, stratum], self.totals[name, stratum], stratum=stratum)
            for name in METRICS
            for stratum in self._strata(name)
        ]

    def _strata(self, name: str) -> tuple[str, ...]:
        if name == "nonvegetation_proposal_share":
            return ("all", *SIZE_STRATA, "negative", "unassessable")
        return ("all", *SIZE_STRATA)


def _record_regions(
    counts: ProposalCounts, kind: str, regions: Iterable[RegionRecovery], image_pixels: int
) -> None:
    for region in regions:
        if not region.pixels:
            continue
        size = vegetation_stratum(region.pixels, image_pixels)
        counts.add(f"{kind}_iou_recall", size, int(region.iou), 1)
        counts.add(f"{kind}_coverage_recall", size, int(region.coverage), 1)


def score_proposals(
    counts: ProposalCounts,
    truth: Masks,
    proposals: Sequence[BoolMask],
    instances: Sequence[BoolMask],
) -> None:
    retained = proposals[:PROPOSAL_LIMIT]
    union = np.zeros_like(truth.vegetation)
    background = ~truth.vegetation & ~truth.void
    stratum = truth.stratum
    for proposal in retained:
        union |= proposal
        total = int(np.count_nonzero(proposal))
        if total:
            confirmed = int(np.count_nonzero(proposal & background))
            counts.add(
                "nonvegetation_proposal_share",
                stratum,
                int(confirmed >= BACKGROUND_THRESHOLD * total),
                1,
            )
    pixels = sparse_coverage(truth.vegetation, union)
    if pixels.labelled_pixels:
        # Per photo, not per pixel: pixels within a photo are not independent samples.
        half = 2 * pixels.covered_labelled_pixels >= pixels.labelled_pixels
        counts.add("half_covered_images", stratum, int(half), 1)
    _record_regions(counts, "component", _component_recovery(truth, retained), union.size)
    plants = (_instance_recovery(instance, ~truth.void, retained) for instance in instances)
    _record_regions(counts, "potted_plant", plants, union.size)


def proposal_metrics(
    truth: Masks, proposals: Sequence[BoolMask], instances: Sequence[BoolMask]
) -> list[Rate]:
    counts = ProposalCounts()
    score_proposals(counts, truth, proposals, instances)
    return counts.metrics()
