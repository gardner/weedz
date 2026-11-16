"""Immutable base events never become authority to replace source claims."""

import json

import pytest
from test_human_import_decode_budget import save
from test_human_import_final_closure import repack
from test_human_import_pipeline import inputs

from weedz.annotation.import_pipeline import import_reviews
from weedz.annotation.import_records import completed_records
from weedz.contract import Annotation, Completeness, ReviewEvent, Sample, revise_sample


@pytest.mark.parametrize("operation", ["replacement", "cancellation", "same-revision"])
def test_source_history_collision_cannot_own_or_skip_an_imported_record(tmp_path, operation):
    request, task, _ = inputs(tmp_path)
    record = completed_records(task, request.namespace)[0]
    provenance = json.loads((request.package / "private/provenance.json").read_bytes())
    original = Sample.model_validate(provenance["samples"][0]["sample"])
    assert original.media.sha256 is not None
    note = Annotation(
        id="source-box",
        supervision="box",
        taxon="Ulex europaeus",
        label="present",
        origin="source",
        box=(1, 1, 5, 5),
    )
    coverage = Completeness(
        id="source-coverage",
        media_sha256=original.media.sha256,
        task="detection",
        taxa=("Ulex europaeus",),
        status="unknown",
        origin="source",
    )
    payload = {
        "annotation_revision_key": record.key,
        "annotations": [note.model_dump(mode="json")],
        "completeness": coverage.model_dump(mode="json"),
    }
    if operation == "same-revision":
        payload.update(
            annotation_revision_key="unrelated-source-key", revision_sha256=record.sha256
        )
    event = ReviewEvent.model_validate(
        dict(
            id=record.revision if operation == "same-revision" else "source-event",
            sample_id=original.id,
            media_sha256=original.media.sha256,
            origin="source",
            actor="source-archive",
            recorded_at="2026-11-16T00:00:00Z",
            action="recorded",
            dimension="annotation",
            payload=payload,
        )
    )
    sample = revise_sample(
        original, annotations=[note], completeness=[coverage], review_history=[event]
    )
    provenance["samples"][0]["sample"] = sample.model_dump(mode="json")
    raw = json.dumps(provenance).encode()
    request = repack(request, {"private/provenance.json": raw})
    if operation == "cancellation":
        task["annotations"][0].update(
            was_cancelled=True, updated_at="2026-11-16T02:00:00Z", result=[]
        )
    output = tmp_path / "collision"
    with pytest.raises(ValueError, match="source history"):
        import_reviews(save(request, task), output)
    assert not output.exists()
    assert (request.package / "private/provenance.json").read_bytes() == raw
