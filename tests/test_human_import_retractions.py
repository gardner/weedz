"""Retractions affect only their own recorded annotation, never other people's claims."""

import hashlib
import json
from dataclasses import replace

from test_human_import_pipeline import inputs

from weedz.annotation.import_pipeline import import_reviews
from weedz.manifest import read_manifest


def test_cancelled_geometry_keeps_other_annotation_and_can_later_reopen(tmp_path):
    request, task, _ = inputs(tmp_path)
    first = task["annotations"][0]
    first["result"].append(
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
    other = json.loads(json.dumps(first))
    other.update(id=3, completed_by=4)
    task["annotations"].append(other)
    request.export.write_text(json.dumps([task]))
    request = replace(
        request, export_sha256=hashlib.sha256(request.export.read_bytes()).hexdigest()
    )
    output = tmp_path / "first"
    import_reviews(request, output)
    initial = read_manifest(output / "samples.jsonl")[0]
    assert len(initial.annotations) == 2
    original = json.loads(json.dumps(first))
    first.update(was_cancelled=True, updated_at="2026-11-16T02:00:00Z", updated_by=9, result=[])
    task["annotations"] = [first]  # Omission of the other account's annotation is not retraction.
    request.export.write_text(json.dumps([task]))
    request = replace(
        request, export_sha256=hashlib.sha256(request.export.read_bytes()).hexdigest()
    )
    retracted = tmp_path / "retracted"
    import_reviews(
        request,
        retracted,
        previous=output,
        previous_sha256=hashlib.sha256((output / "manifest.json").read_bytes()).hexdigest(),
    )
    current = read_manifest(retracted / "samples.jsonl")[0]
    assert len(current.annotations) == len(current.completeness) == 1
    assert current.annotations[0].author == "label-studio:synthetic-project:account:4"
    assert current.review_history[-1].actor == "label-studio:synthetic-project:account:9"
    assert len(current.review_history) == 3
    original.update(updated_at="2026-11-16T03:00:00Z", updated_by=9)
    task["annotations"] = [original]
    request.export.write_text(json.dumps([task]))
    request = replace(
        request, export_sha256=hashlib.sha256(request.export.read_bytes()).hexdigest()
    )
    reopened = tmp_path / "reopened"
    import_reviews(
        request,
        reopened,
        previous=retracted,
        previous_sha256=hashlib.sha256((retracted / "manifest.json").read_bytes()).hexdigest(),
    )
    final = read_manifest(reopened / "samples.jsonl")[0]
    assert len(final.annotations) == 2 and len(final.review_history) == 4
    assert final.review_history[-1].supersedes == current.review_history[-1].id
