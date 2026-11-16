"""A pinned previous package must still preserve its immutable source evidence."""

import hashlib
import json

import pytest
from test_human_import_final_closure import repack
from test_human_import_pipeline import inputs

from weedz.annotation.import_pipeline import import_reviews


def source_with_evidence(request):
    provenance = json.loads((request.package / "private/provenance.json").read_bytes())
    sample = provenance["samples"][0]["sample"]
    sample.update(
        schema_version=2,
        annotations=[
            dict(
                id="source-box",
                supervision="box",
                taxon="Ulex europaeus",
                label="present",
                origin="source",
                box=[1, 1, 5, 5],
            )
        ],
        completeness=[
            dict(
                id="source-coverage",
                media_sha256=sample["media"]["sha256"],
                task="detection",
                taxa=["Ulex europaeus"],
                status="unknown",
                origin="source",
            )
        ],
        review_history=[
            dict(
                id="source-event",
                sample_id=sample["id"],
                media_sha256=sample["media"]["sha256"],
                origin="source",
                actor="archive",
                recorded_at="2026-11-16T00:00:00Z",
                action="recorded",
                dimension="annotation",
                payload={},
            )
        ],
    )
    for field in ("annotations", "completeness", "review_history"):
        sample[field].append({**sample[field][0], "id": sample[field][0]["id"] + "-second"})
    return repack(request, {"private/provenance.json": json.dumps(provenance).encode()})


@pytest.mark.parametrize("field", ["annotations", "completeness", "review_history"])
@pytest.mark.parametrize("operation", ["remove", "change", "reorder"])
def test_rehashed_previous_cannot_remove_or_change_base_evidence(tmp_path, field, operation):
    request, _, _ = inputs(tmp_path)
    request = source_with_evidence(request)
    prior = tmp_path / "prior"
    receipt = import_reviews(request, prior)
    row = json.loads((prior / "samples.jsonl").read_bytes())
    if operation == "remove":
        row[field] = [item for item in row[field] if not item["id"].startswith("source-")]
    elif operation == "reorder":
        row[field][:2] = reversed(row[field][:2])
    else:
        original = next(item for item in row[field] if item["id"].startswith("source-"))
        original[
            {"annotations": "taxon", "completeness": "author", "review_history": "actor"}[field]
        ] = "changed"
    provenance = json.loads((prior / "private/provenance.json").read_bytes())
    provenance["samples"][0]["sample"] = row
    provenance_bytes = json.dumps(provenance).encode()
    (prior / "private/provenance.json").write_bytes(provenance_bytes)
    receipt["files"]["private/provenance.json"] = hashlib.sha256(provenance_bytes).hexdigest()
    raw = (json.dumps(row) + "\n").encode()
    (prior / "samples.jsonl").write_bytes(raw)
    receipt["files"]["samples.jsonl"] = hashlib.sha256(raw).hexdigest()
    manifest = json.dumps(receipt).encode()
    (prior / "manifest.json").write_bytes(manifest)
    output = tmp_path / "refused"
    with pytest.raises(ValueError, match="source evidence"):
        import_reviews(
            request, output, previous=prior, previous_sha256=hashlib.sha256(manifest).hexdigest()
        )
    assert not output.exists()


def test_source_evidence_survives_normal_importer_additions_and_replay(tmp_path):
    request, _, _ = inputs(tmp_path)
    request = source_with_evidence(request)
    first = tmp_path / "first"
    import_reviews(request, first)
    second = tmp_path / "second"
    import_reviews(
        request,
        second,
        previous=first,
        previous_sha256=hashlib.sha256((first / "manifest.json").read_bytes()).hexdigest(),
    )
    assert (first / "samples.jsonl").read_bytes() == (second / "samples.jsonl").read_bytes()
