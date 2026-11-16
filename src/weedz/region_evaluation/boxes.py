"""Labelled-region proposal recall, separate from matched crop identification."""

import math
from collections.abc import Sequence
from dataclasses import asdict
from pathlib import Path

from weedz.classification.batch import _snapshot
from weedz.contract import Sample
from weedz.region_evaluation.classifier_inputs import RegionalClassifications
from weedz.region_evaluation.geometry import Box, box_iou
from weedz.region_evaluation.identification import score_identification
from weedz.region_evaluation.matching import match_regions
from weedz.region_evaluation.proposal_inputs import ProposalBatch
from weedz.region_evaluation.taxonomy import TaxonomyMapping
from weedz.region_evaluation.truth import TruthOrigin, labelled_boxes

THRESHOLDS = tuple(value / 100 for value in range(50, 100, 5))
BUDGETS = (1, 10, 100)


def box_report(
    samples: Sequence[Sample],
    assets_root: Path,
    proposed: ProposalBatch,
    *,
    thresholds: tuple[float, ...] = THRESHOLDS,
    budgets: tuple[int, ...] = BUDGETS,
    classifier: RegionalClassifications | None = None,
    taxonomy: TaxonomyMapping | None = None,
    max_source_bytes: int | None = None,
    truth_origin: TruthOrigin = "source",
) -> list[dict]:
    _protocol(thresholds, budgets)
    if (classifier is None) != (taxonomy is None):
        raise ValueError(
            "Identification requires both classifier evidence and an explicit taxonomy map"
        )
    root = assets_root.resolve(strict=True)
    reports = []
    for sample in samples:
        _snapshot(sample, root, max_source_bytes)
        width, height = sample.media.width, sample.media.height
        if width is None or height is None:
            raise ValueError("Box evaluation requires source geometry")
        truth = labelled_boxes(sample.annotations, size=(width, height), origin=truth_origin)
        stage = proposed.rows[sample.id]["segmentation"]
        regions = stage["regions"]
        boxes = _boxes(regions, (width, height))
        overlaps = [[box_iou(label.box, box) for box in boxes] for label in truth]
        measurements = []
        for budget in budgets:
            for threshold in thresholds:
                matching = match_regions(
                    [row[:budget] for row in overlaps],
                    threshold=threshold,
                    proposal_count=min(budget, len(regions)),
                )
                identified = None
                if classifier is not None and taxonomy is not None:
                    identified = score_identification(
                        sample,
                        truth,
                        regions[:budget],
                        classifier.rows[sample.id],
                        taxonomy,
                        matching,
                        truth_origin=truth_origin,
                    )
                measurements.append(
                    {
                        "budget": budget,
                        "actual_proposals": min(budget, len(regions)),
                        "iou_threshold": threshold,
                        "labelled_regions": len(truth),
                        "matched_labelled_regions": len(matching.matches),
                        "missed_labelled_regions": len(matching.missed_truth),
                        "labelled_region_recall": len(matching.matches) / len(truth)
                        if truth
                        else None,
                        "unmatched_proposals": len(matching.unmatched_proposals),
                        "matches": [
                            {
                                "annotation_id": truth[pair.truth].id,
                                "proposal_id": regions[pair.proposal]["id"],
                                "iou": pair.overlap,
                            }
                            for pair in matching.matches
                        ],
                        "identification": identified,
                    }
                )
        reports.append(
            {
                "sample_id": sample.id,
                "image_sha256": sample.media.sha256,
                "source": sample.source,
                "rights": sample.rights.model_dump(mode="json"),
                "source_context": dict(sample.context),
                "source_groups": dict(sample.groups),
                "proposal_status": stage["status"],
                "proposal_count": len(regions),
                "truth_boxes": [asdict(label) for label in truth],
                "measurements": measurements,
            }
        )
    return reports


def _protocol(thresholds: tuple[float, ...], budgets: tuple[int, ...]) -> None:
    if not thresholds or any(
        type(v) not in (int, float) or not math.isfinite(v) or not 0 < v <= 1 for v in thresholds
    ):
        raise ValueError("Declare finite IoU thresholds in (0, 1]")
    if not budgets or any(type(v) is not int or not 1 <= v <= 1000 for v in budgets):
        raise ValueError("Declare integer proposal budgets in [1, 1000]")
    if len(set(thresholds)) != len(thresholds) or len(set(budgets)) != len(budgets):
        raise ValueError("Evaluation thresholds and budgets cannot repeat")


def _boxes(regions: list[dict], size: tuple[int, int]) -> list[Box]:
    if len(regions) > 1000 or len({row["id"] for row in regions}) != len(regions):
        raise ValueError("Duplicate or excessive proposal identities")
    boxes = []
    for region in regions:
        raw = region["box"]
        if len(raw) != 4 or any(type(value) not in (int, float) for value in raw):
            raise ValueError("Proposal box must use four finite source coordinates")
        left, top, right, bottom = raw
        box = (float(left), float(top), float(right), float(bottom))
        box_iou(box, box)
        if right > size[0] or bottom > size[1]:
            raise ValueError("Proposal box escapes source frame")
        boxes.append(box)
    return boxes
