"""Pending imported human regions remain visible without becoming training truth."""

from test_human_import_decode_budget import save
from test_human_import_pipeline import inputs

from weedz.annotation.import_pipeline import import_reviews
from weedz.manifest import read_manifest
from weedz.reference import collection


def test_pending_imported_region_is_preserved_but_has_no_reference_use(tmp_path):
    request, task, _ = inputs(tmp_path)
    rows = task["annotations"][0]["result"]
    next(row for row in rows if row["from_name"] == "review_status")["value"]["choices"] = [
        "unreviewed"
    ]
    rows.append(
        dict(
            id="box",
            from_name="review_boxes",
            to_name="image",
            type="rectanglelabels",
            original_width=10,
            original_height=10,
            image_rotation=0,
            value=dict(
                x=10, y=20, width=50, height=40, rotation=0, rectanglelabels=["Ulex europaeus"]
            ),
        )
    )
    output = tmp_path / "pending"
    receipt = import_reviews(save(request, task), output)
    samples = read_manifest(output / "samples.jsonl", receipt["files"]["samples.jsonl"])
    original = samples[0].model_dump(mode="json")
    report = collection("synthetic pending review", samples)
    assert len(report["examples"]) == 1
    assert report["examples"][0]["standing"] == "unreviewed"
    assert all(
        report["uses"][use]["eligible"] == 0 for use in ("training", "evaluation", "sharing")
    )
    assert samples[0].annotations[0].review == "unreviewed"
    assert len(samples[0].review_history) == 1
    assert samples[0].model_dump(mode="json") == original
