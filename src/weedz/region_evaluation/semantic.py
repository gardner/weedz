"""Sparse source-pixel coverage from closed proposals; no inferred negative labels."""

from collections.abc import Sequence
from dataclasses import asdict
from pathlib import Path
from typing import Literal

import numpy as np

from weedz.classification.batch import _snapshot
from weedz.contract import Sample
from weedz.region_evaluation.assets import read_binary_mask
from weedz.region_evaluation.coverage import sparse_coverage
from weedz.region_evaluation.pixels import pixel_sha256
from weedz.region_evaluation.proposal_inputs import ProposalBatch, proposal_status
from weedz.region_evaluation.proposal_masks import proposal_mask
from weedz.region_evaluation.truth import TruthOrigin, eligible_positive


def sparse_report(
    samples: Sequence[Sample],
    assets_root: Path,
    proposed: ProposalBatch,
    *,
    kind: Literal["sam2", "sam3"],
    budgets: tuple[int, ...] = (1, 10, 100),
    max_source_bytes: int | None = None,
    truth_origin: TruthOrigin = "source",
) -> list[dict]:
    """Measure source-labelled support only; label granularity stays semantic/sparse."""
    if not budgets or any(type(value) is not int or not 1 <= value <= 1000 for value in budgets):
        raise ValueError("Declare bounded positive proposal budgets")
    if len(set(budgets)) != len(budgets):
        raise ValueError("Proposal budgets cannot repeat")
    root = assets_root.resolve(strict=True)
    reports = []
    for sample in samples:
        encoded = _snapshot(sample, root, max_source_bytes)
        stage = proposed.rows[sample.id]["segmentation"]
        width, height = sample.media.width, sample.media.height
        if width is None or height is None:
            raise ValueError("Sparse evaluation requires source geometry")
        size = (width, height)
        assessed = read_binary_mask(
            root,
            sample.context["assessed_mask_uri"],
            sample.context["assessed_mask_sha256"],
            size=size,
        )
        unions = _unions(stage["regions"], size, kind, budgets)
        labels = _labels(sample, root, size, assessed, unions, truth_origin)
        reports.append(
            {
                "sample_id": sample.id,
                "image_sha256": sample.media.sha256,
                "decoded_pixel_sha256": pixel_sha256(encoded),
                "source": sample.source,
                "source_context": dict(sample.context),
                "source_groups": dict(sample.groups),
                "proposal_status": proposal_status(stage),
                "proposal_count": len(stage["regions"]),
                "labels": labels,
            }
        )
    return reports


def _unions(records: list[dict], size, kind, budgets: tuple[int, ...]) -> dict[int, np.ndarray]:
    if len(records) > 1000 or len({row["id"] for row in records}) != len(records):
        raise ValueError("Duplicate or excessive proposal identities")
    union = np.zeros((size[1], size[0]), dtype=bool)
    results = {}
    start = 0
    for budget in sorted(budgets):
        for record in records[start:budget]:
            union |= proposal_mask(record, size=size, kind=kind)
        results[budget] = union.copy()
        start = budget
    return results


def _labels(
    sample: Sample, root: Path, size, assessed: np.ndarray, unions: dict, origin: TruthOrigin
) -> list[dict]:
    labels = []
    for label in sample.annotations:
        if label.supervision != "sparse_mask" or not eligible_positive(label, origin=origin):
            continue
        if not label.mask_uri or not label.mask_sha256:
            raise ValueError("Sparse truth requires a pinned mask")
        truth = read_binary_mask(root, label.mask_uri, label.mask_sha256, size=size)
        labels.append(
            {
                "annotation_id": label.id,
                "taxon": label.taxon,
                "category": label.category,
                "origin": label.origin,
                "review": label.review,
                "mask_sha256": label.mask_sha256,
                "budgets": [
                    {"budget": budget, **asdict(sparse_coverage(truth, union, assessed=assessed))}
                    for budget, union in unions.items()
                ],
            }
        )
    if not labels:
        raise ValueError("No eligible source/reviewed sparse labels; no denominator")
    return labels
