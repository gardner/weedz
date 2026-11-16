"""Integration of closed source pixels, sparse labels and fixed proposal order."""

import hashlib
from pathlib import Path

import numpy as np
import pytest
from PIL import Image
from region_helpers import sample

from weedz.region_evaluation.proposal_inputs import ProposalBatch
from weedz.region_evaluation.semantic import sparse_report
from weedz.segmentation.regions import region_from_mask


def inputs(root: Path):
    Image.new("RGB", (2, 2)).save(root / "image.png")
    truth = np.array([[True, False], [False, False]])
    Image.fromarray(truth.astype(np.uint8) * 255).save(root / "truth.png")
    image_sha = hashlib.sha256((root / "image.png").read_bytes()).hexdigest()
    mask_sha = hashlib.sha256((root / "truth.png").read_bytes()).hexdigest()
    record = sample(
        media={"uri": "image.png", "sha256": image_sha, "width": 2, "height": 2},
        annotations=[
            {
                "id": "human:weed",
                "supervision": "sparse_mask",
                "category": "weed",
                "label": "present",
                "origin": "source",
                "mask_uri": "truth.png",
                "mask_sha256": mask_sha,
            }
        ],
        context={"assessed_mask_uri": "truth.png", "assessed_mask_sha256": mask_sha},
    )
    masks = [~truth, truth]
    regions = [
        region_from_mask(
            Image.new("RGB", (2, 2)), mask, {}, max_side=64, context_fraction=0
        ).record()
        for mask in masks
    ]
    proposed = ProposalBatch(
        "a" * 64,
        "b" * 64,
        "c" * 64,
        "fixture:v1",
        {record.id: {"segmentation": {"status": "ok", "regions": regions}}},
    )
    return record, proposed


def test_sparse_report_keeps_budget_order_and_never_scores_unknown_background(
    tmp_path: Path,
) -> None:
    record, proposed = inputs(tmp_path)
    report = sparse_report([record], tmp_path, proposed, kind="sam2", budgets=(1, 10))
    first, second = report[0]["labels"][0]["budgets"]
    assert first["coverage"] == 0
    assert second["coverage"] == 1
    assert second["assessed_labelled_pixels"] == 1
    assert "false_positives" not in second
    assert "dice" not in second


def test_replaced_source_pixels_cannot_inherit_the_label_and_proposal_join(tmp_path: Path) -> None:
    record, proposed = inputs(tmp_path)
    Image.new("RGB", (2, 2), "white").save(tmp_path / "image.png")
    with pytest.raises(ValueError, match="checksum"):
        sparse_report([record], tmp_path, proposed, kind="sam2")
