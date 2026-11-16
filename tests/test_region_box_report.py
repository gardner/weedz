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


def test_large_supported_case_has_explicit_bounded_receipt(tmp_path):
    import json

    from weedz.batches.receipts import write_receipt
    from weedz.contract import revise_sample
    from weedz.region_evaluation.cli import CASE_RECEIPT_BYTES

    record, proposed = inputs(tmp_path)
    # Long, valid source IDs repeat across the actual protocol's matched-pair grid.
    annotations = [
        record.annotations[0].model_copy(update={"id": f"source:{i}:" + "x" * 3000})
        for i in range(40)
    ]
    record = revise_sample(record, annotations=annotations)
    proposed.rows[record.id]["segmentation"]["regions"] = [
        {"id": f"proposal:{i}", "box": [0, 0, 2, 2]} for i in range(40)
    ]
    case = box_report([record], tmp_path, proposed)[0]
    assert len(json.dumps(case).encode()) > 1024 * 1024
    with pytest.raises(ValueError, match="cap"):
        write_receipt(tmp_path, "default.json", case)
    write_receipt(tmp_path, "case.json", case, maximum_bytes=CASE_RECEIPT_BYTES)


def test_equal_pixels_with_different_png_encoding_block_primary_aggregate(tmp_path):
    from weedz.contract import revise_sample
    from weedz.region_evaluation.aggregate import aggregate_boxes

    record, proposed = inputs(tmp_path)
    Image.new("RGB", (4, 4)).save(tmp_path / "alias.png", compress_level=0)
    raw = (tmp_path / "alias.png").read_bytes()
    alias = revise_sample(
        record,
        id="cwfid:alias",
        source_id="alias",
        media={
            **record.media.model_dump(),
            "uri": "alias.png",
            "sha256": hashlib.sha256(raw).hexdigest(),
        },
    )
    assert alias.media.sha256 != record.media.sha256
    proposed.rows[alias.id] = proposed.rows[record.id]
    cases = box_report([record, alias], tmp_path, proposed)
    assert cases[0]["decoded_pixel_sha256"] == cases[1]["decoded_pixel_sha256"]
    assert aggregate_boxes(cases)["aggregate"] is None


@pytest.mark.parametrize("maximum", [0, True, 32 * 1024 * 1024 + 1])
def test_receipt_override_is_bounded_before_publication(tmp_path, maximum):
    from weedz.batches.receipts import write_receipt

    with pytest.raises(ValueError, match="cap"):
        write_receipt(tmp_path, "case.json", {}, maximum_bytes=maximum)
    assert not (tmp_path / "case.json").exists()


def test_report_keeps_proposal_success_when_crop_classification_failed(tmp_path):
    record, proposed = inputs(tmp_path)
    proposed.rows[record.id]["segmentation"].update(
        status="failed", proposal_status="ok", view_status="failed"
    )
    assert box_report([record], tmp_path, proposed)[0]["proposal_status"] == "ok"
