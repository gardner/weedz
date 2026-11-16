"""Independent source boxes produce labelled-region metrics, never mask accuracy."""

import hashlib
from pathlib import Path

import pytest
from PIL import Image
from region_helpers import sample

from weedz.region_evaluation.boxes import box_report
from weedz.region_evaluation.proposal_inputs import ProposalBatch


def inputs(root: Path):
    Image.new("RGB", (4, 4)).save(root / "image.png")
    image_sha = hashlib.sha256((root / "image.png").read_bytes()).hexdigest()
    record = sample(
        media={"uri": "image.png", "sha256": image_sha, "width": 4, "height": 4},
        annotations=[
            {
                "id": "source:1",
                "supervision": "box",
                "box": [0, 0, 2, 2],
                "taxon": "Species alba",
                "label": "present",
                "origin": "source",
            },
            {
                "id": "source:2",
                "supervision": "box",
                "box": [2, 2, 4, 4],
                "taxon": "Species rubra",
                "label": "present",
                "origin": "source",
            },
        ],
    )
    regions = [{"id": "proposal:1", "box": [0, 0, 2, 2]}, {"id": "proposal:2", "box": [0, 2, 1, 4]}]
    proposed = ProposalBatch(
        "a" * 64,
        "b" * 64,
        "c" * 64,
        "sam:v1",
        {record.id: {"segmentation": {"status": "ok", "regions": regions}}},
    )
    return record, proposed


def test_report_counts_proposal_misses_separately_from_unassessed_proposals(tmp_path: Path):
    record, proposed = inputs(tmp_path)
    report = box_report([record], tmp_path, proposed, thresholds=(0.5,), budgets=(1, 10))
    first, second = report[0]["measurements"]
    assert first["labelled_regions"] == second["labelled_regions"] == 2
    assert second["matched_labelled_regions"] == second["missed_labelled_regions"] == 1
    assert second["labelled_region_recall"] == 0.5
    assert first["actual_proposals"] == 1 and second["actual_proposals"] == 2
    assert second["unmatched_proposals"] == 1
    assert "false_positives" not in second
    assert "dice" not in second


def test_model_box_outside_source_frame_refused(tmp_path: Path):
    record, proposed = inputs(tmp_path)
    proposed.rows[record.id]["segmentation"]["regions"][0]["box"] = [0, 0, 5, 5]
    with pytest.raises(ValueError, match="frame"):
        box_report([record], tmp_path, proposed)
