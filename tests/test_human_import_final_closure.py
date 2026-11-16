"""Generated metadata may not replace an existing referenced asset or pinned snapshot."""

import hashlib
import json
from dataclasses import replace
from io import BytesIO

import pytest
from PIL import Image
from test_human_import_pipeline import inputs

from weedz.annotation.import_package import read_package
from weedz.annotation.import_pipeline import import_reviews
from weedz.contract import Annotation, ReviewEvent, Sample, revise_sample


def repack(request, updates, removed=()):
    manifest = json.loads((request.package / "manifest.json").read_bytes())
    for name in removed:
        (request.package / name).unlink()
        del manifest["files"][name]
    for name, raw in updates.items():
        path = request.package / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
        manifest["files"][name] = hashlib.sha256(raw).hexdigest()
    raw = json.dumps(manifest).encode()
    (request.package / "manifest.json").write_bytes(raw)
    return replace(request, package_sha256=hashlib.sha256(raw).hexdigest())


@pytest.mark.parametrize("kind", ["media", "mask", "history", "history-claim", "assessed"])
def test_generated_samples_metadata_cannot_replace_a_source_asset(tmp_path, kind):
    request, task, _ = inputs(tmp_path)
    next(
        row for row in task["annotations"][0]["result"] if row["from_name"] == "completeness_status"
    )["value"]["choices"] = ["partial"]
    provenance = json.loads((request.package / "private/provenance.json").read_bytes())
    sample = Sample.model_validate(provenance["samples"][0]["sample"])
    removed = []
    if kind == "media":
        protected = (request.package / sample.media.uri).read_bytes()
        removed.append(sample.media.uri)
        sample = revise_sample(sample, media={**sample.media.model_dump(), "uri": "samples.jsonl"})
        task["data"]["image"] = "/data/local-files/?d=samples.jsonl"
    else:
        encoded = BytesIO()
        Image.new("L", (10, 10), 255).save(encoded, format="PNG")
        protected = encoded.getvalue()
        sha = hashlib.sha256(protected).hexdigest()
        note = Annotation(
            id="source-mask",
            supervision="dense_mask",
            taxon="Ulex europaeus",
            label="present",
            origin="source",
            mask_uri="samples.jsonl",
            mask_sha256=sha,
        )
        if kind == "mask":
            sample = revise_sample(sample, annotations=[note])
        elif kind in {"history", "history-claim"}:
            assert sample.media.sha256 is not None
            event = ReviewEvent.model_validate(
                dict(
                    id="old-source",
                    sample_id=sample.id,
                    media_sha256=sample.media.sha256,
                    origin="source",
                    actor="fixture-source",
                    action="recorded",
                    dimension="annotation",
                    payload=(
                        {"annotations": [note.model_dump(mode="json")]}
                        if kind == "history"
                        else {"claim": note.model_dump(mode="json")}
                    ),
                )
            )
            sample = revise_sample(sample, review_history=[event])
        else:
            sample = revise_sample(
                sample, context={"assessed_mask_uri": "samples.jsonl", "assessed_mask_sha256": sha}
            )
    provenance["samples"][0]["sample"] = sample.model_dump(mode="json")
    canonical = json.loads((request.package / "tasks.json").read_bytes())
    canonical[0]["data"] = task["data"]
    request = repack(
        request,
        {
            "samples.jsonl": protected,
            "tasks.json": json.dumps(canonical).encode(),
            "private/provenance.json": json.dumps(provenance).encode(),
        },
        removed,
    )
    request.export.write_text(json.dumps([task]), encoding="utf-8")
    request = replace(
        request, export_sha256=hashlib.sha256(request.export.read_bytes()).hexdigest()
    )
    read_package(request.package, request.package_sha256)  # A valid captured source package.
    output = tmp_path / "corrupted"
    with pytest.raises(ValueError, match="asset"):
        import_reviews(request, output)
    assert not output.exists()
    assert (request.package / "samples.jsonl").read_bytes() == protected


@pytest.mark.parametrize("snapshot", ["source-provenance", "exports", "configs"])
@pytest.mark.parametrize("identical", [False, True])
def test_immutable_snapshot_paths_refuse_conflicts_and_allow_exact_reuse(
    tmp_path, snapshot, identical
):
    request, _, _ = inputs(tmp_path)
    if snapshot == "source-provenance":
        expected = (request.package / "private/provenance.json").read_bytes()
        checksum, suffix = hashlib.sha256(expected).hexdigest(), "json"
    elif snapshot == "exports":
        expected, checksum, suffix = request.export.read_bytes(), request.export_sha256, "json"
    else:
        expected, checksum, suffix = request.config.read_bytes(), request.config_sha256, "xml"
    name = f"private/{snapshot}/{checksum}.{suffix}"
    original = expected if identical else b"Different retained source bytes"
    request = repack(request, {name: original})
    output = tmp_path / "output"
    if identical:
        import_reviews(request, output)
        checksum = hashlib.sha256((output / "manifest.json").read_bytes()).hexdigest()
        read_package(output, checksum)
        assert (output / name).read_bytes() == expected
    else:
        with pytest.raises(ValueError, match="snapshot"):
            import_reviews(request, output)
        assert not output.exists()
    assert (request.package / name).read_bytes() == original


def test_unreferenced_canonical_metadata_can_be_updated_and_replayed(tmp_path):
    request, _, _ = inputs(tmp_path)
    original = json.loads((request.package / "private/provenance.json").read_bytes())["samples"][0][
        "sample"
    ]
    source_metadata = json.dumps(original).encode() + b"\n"
    request = repack(request, {"samples.jsonl": source_metadata})
    output = tmp_path / "reviewed"
    import_reviews(request, output)
    checksum = hashlib.sha256((output / "manifest.json").read_bytes()).hexdigest()
    read_package(output, checksum)
    import_reviews(request, tmp_path / "repeat", previous=output, previous_sha256=checksum)
    assert (request.package / "samples.jsonl").read_bytes() == source_metadata
