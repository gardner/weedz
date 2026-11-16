"""Source labels remain useful; pending human declarations remain preserved evidence."""

import hashlib

import pytest

from weedz.contract import Annotation, Sample
from weedz.release_scope import task_annotations


def test_pending_human_region_is_not_task_evidence_but_source_labels_remain_usable():
    note = Annotation(
        id="human",
        supervision="box",
        taxon="Ulex europaeus",
        label="present",
        box=(0, 0, 10, 10),
        origin="reviewer",
        author="account:1",
    )
    value = dict(
        id="fixture:1",
        source="fixture",
        source_id="1",
        snapshot="v1",
        rights=dict(
            media_license="cc0",
            metadata_license="cc0",
            attribution="Fixture",
            license_source="https://example.org",
        ),
        media=dict(uri="image.png", sha256="a" * 64, width=10, height=10),
        tasks=["inference"],
        annotations=[note],
    )
    sample = Sample.model_validate(value)
    original = sample.model_dump_json()
    assert not note.supervises()
    assert task_annotations(sample, "detection") == ()
    assert Sample.model_validate_json(original).model_dump_json() == original
    source = Annotation.model_validate(note.model_dump() | {"origin": "source", "author": None})
    accepted = Annotation.model_validate(
        note.model_dump() | {"review": "accepted", "reviewers": ["account:2"]}
    )
    assert source.supervises() and accepted.supervises()
    assert sample.schema_version == 1
    with pytest.raises(ValueError, match="needs box supervision"):
        Sample.model_validate(value | {"tasks": ["detection"]})
    source_sample = Sample.model_validate(value | {"annotations": [source], "tasks": ["detection"]})
    assert source_sample.schema_version == 1
    assert hashlib.sha256(source_sample.model_dump_json().encode()).hexdigest() == (
        "88a2e8eda5ea5429ed80bec0a4a2e94cd7655d80f94cc696de178d571aa882bd"
    )


def test_completed_but_unreviewed_import_preserves_regions_without_supervision(tmp_path):
    import hashlib
    import json
    from dataclasses import replace

    from test_human_import_pipeline import inputs

    from weedz.annotation.import_pipeline import import_reviews
    from weedz.manifest import read_manifest

    request, task, _ = inputs(tmp_path)
    results = task["annotations"][0]["result"]
    next(row for row in results if row["from_name"] == "review_status")["value"]["choices"] = [
        "unreviewed"
    ]
    results.append(
        dict(
            id="pending-box",
            from_name="review_boxes",
            to_name="image",
            type="rectanglelabels",
            original_width=10,
            original_height=10,
            image_rotation=0,
            value=dict(
                x=10, y=10, width=50, height=50, rotation=0, rectanglelabels=["Ulex europaeus"]
            ),
        )
    )
    request.export.write_text(json.dumps([task]), encoding="utf-8")
    request = replace(
        request, export_sha256=hashlib.sha256(request.export.read_bytes()).hexdigest()
    )
    output = tmp_path / "pending-import"
    import_reviews(request, output)
    sample = read_manifest(output / "samples.jsonl")[0]
    assert sample.annotations[0].review == "unreviewed"
    assert not sample.annotations[0].supervises()
    assert sample.review_history[0].payload["annotations"]
    assert sample.tasks == frozenset({"inference"})
