"""Canonical manifests export without inventing iNaturalist observation identities."""

import hashlib
import json
from pathlib import Path

import pytest
from PIL import Image
from test_annotation_auto_labels import region
from test_annotation_versions import metadata

from weedz.annotation.samples import export_samples
from weedz.contract import Media, Rights, Sample
from weedz.manifest import write_manifest


@pytest.fixture
def canonical_batch(tmp_path: Path):
    root = tmp_path / "batch"
    (root / "images").mkdir(parents=True)
    image = root / "images/source.png"
    Image.new("RGB", (6, 4), "green").save(image)
    digest = hashlib.sha256(image.read_bytes()).hexdigest()
    sample = Sample(
        id="deepweeds:real-source.jpg",
        source="deepweeds",
        source_id="real-source.jpg",
        snapshot="pinned",
        rights=Rights(
            media_license="CC-BY-4.0",
            metadata_license="CC-BY-4.0",
            attribution="Olsen et al.",
            license_source="https://example.test/source",
        ),
        media=Media(uri=str(image), sha256=digest, width=6, height=4, format="PNG"),
        original_label="Private source class context",
        tasks=frozenset({"inference"}),
    )
    manifest = root / "samples.jsonl"
    manifest_sha = write_manifest(manifest, [sample])
    key = hashlib.sha256(f"{sample.id}:{digest}".encode()).hexdigest()
    frame = root / "frame.json"
    frame.write_text(
        json.dumps(
            {
                "model": {"revision": "pinned"},
                "manifest_sha256": manifest_sha,
                "predictions": [
                    {
                        "external_id": key,
                        "source_id": sample.id,
                        "image_sha256": digest,
                        "topk": [{"taxon": "Cotoneaster integerrimus Medik.", "score": 0.2}],
                    }
                ],
            }
        )
    )
    return manifest, frame, key


def test_canonical_source_identity_and_editable_frame_label(canonical_batch, tmp_path):
    manifest, frame, key = canonical_batch
    output = tmp_path / "export"
    export_samples(manifest, output, frame_results=frame)
    task = json.loads((output / "tasks.json").read_text())[0]
    assert task["meta"]["external_id"] == key
    assert task["data"]["source_dataset"] == "deepweeds"
    assert "Private source class" not in json.dumps(task)
    assert "observation_id" not in json.dumps(task) and "annotations" not in task
    text = next(r for r in task["predictions"][0]["result"] if r["from_name"] == "predicted_taxon")
    assert text["value"]["text"] == ["Cotoneaster integerrimus Medik."]
    assert not text.get("readonly", False)


def test_prediction_must_match_actual_model_input_media(canonical_batch, tmp_path):
    manifest, frame, _ = canonical_batch
    document = json.loads(frame.read_text())
    document["predictions"][0]["image_sha256"] = "0" * 64
    frame.write_text(json.dumps(document))
    output = tmp_path / "bad"
    with pytest.raises(ValueError, match="image.*checksum"):
        export_samples(manifest, output, frame_results=frame)
    assert not output.exists()


@pytest.fixture
def classified_batch(canonical_batch):
    manifest, frame, key = canonical_batch
    frame_doc = json.loads(frame.read_text())
    row = frame_doc["predictions"][0]
    classifier, proposer = metadata()
    proposed_region = region()
    proposed_region["views"] = {}
    proposals = manifest.parent / "proposals.jsonl"
    proposals.write_text(
        json.dumps(
            {
                "sample_id": row["source_id"],
                "image_sha256": row["image_sha256"],
                "segmentation": {
                    "status": "ok",
                    "proposal_status": "ok",
                    "regions": [proposed_region],
                    "provenance": proposer,
                },
            }
        )
        + "\n"
    )
    topk = [{"taxon": "Ulex europaeus L.", "score": 0.8}]
    regional = manifest.parent / "regions.json"
    regional.write_text(
        json.dumps(
            {
                "model": dict(classifier, proposer=proposer),
                "proposals_sha256": hashlib.sha256(proposals.read_bytes()).hexdigest(),
                "predictions": [
                    dict(
                        row,
                        regions=[
                            {"id": proposed_region["id"], "topk": topk, "views": {"masked": topk}}
                        ],
                    )
                ],
            }
        )
    )
    tiled = manifest.parent / "tiles.json"
    tiled.write_text(
        json.dumps(dict(frame_doc, predictions=[dict(row, views=[{"topk": row["topk"]}])]))
    )
    return manifest, frame, proposals, regional, tiled


def test_multiple_real_pipeline_versions_keep_region_taxonomy_and_tile_scope(
    classified_batch, tmp_path
):
    manifest, frame, proposals, regional, tiled = classified_batch
    output = tmp_path / "all-views"
    export_samples(
        manifest,
        output,
        frame_results=frame,
        proposals=proposals,
        regional_results=regional,
        tiled_results=tiled,
    )
    task = json.loads((output / "tasks.json").read_text())[0]
    assert len(task["predictions"]) == 4 and "annotations" not in task
    first = task["predictions"][0]
    assert first["model_version"].startswith("SAM2.1 + PlantCLEF masked v1")
    brush = next(r for r in first["result"] if r["type"] == "brushlabels")
    assert brush["value"]["brushlabels"] == ["Ulex europaeus"]
    assert task["predictions"][-1]["model_version"].startswith("PlantCLEF tiles auto-label")


def test_regional_results_must_bind_the_exact_proposals(classified_batch, tmp_path):
    manifest, frame, proposals, regional, _ = classified_batch
    doc = json.loads(regional.read_text())
    doc["proposals_sha256"] = "0" * 64
    regional.write_text(json.dumps(doc))
    output = tmp_path / "wrong-masks"
    with pytest.raises(ValueError, match="proposal.*checksum"):
        export_samples(
            manifest, output, frame_results=frame, proposals=proposals, regional_results=regional
        )
    assert not output.exists()


def test_frame_results_require_closed_manifest_binding(canonical_batch, tmp_path):
    manifest, frame, _ = canonical_batch
    document = json.loads(frame.read_text())
    del document["manifest_sha256"]
    frame.write_text(json.dumps(document))
    output = tmp_path / "unbound"
    with pytest.raises(ValueError, match="manifest checksum"):
        export_samples(manifest, output, frame_results=frame)
    assert not output.exists()


def test_truncated_canonical_png_is_not_published(canonical_batch, tmp_path):
    manifest, _, _ = canonical_batch
    document = json.loads(manifest.read_text())
    image = Path(document["media"]["uri"])
    truncated = image.read_bytes()[:55]
    image.write_bytes(truncated)
    document["media"]["sha256"] = hashlib.sha256(truncated).hexdigest()
    manifest.write_text(json.dumps(document) + "\n")
    output = tmp_path / "truncated"
    with pytest.raises(OSError):
        export_samples(manifest, output)
    assert not output.exists()


@pytest.mark.parametrize("prefix", ["images with spaces", "hash#mark", "query?mark", "amp&mark"])
def test_custom_image_prefix_is_url_encoded(canonical_batch, tmp_path, prefix):
    from urllib.parse import parse_qs, urlsplit

    manifest, _, _ = canonical_batch
    output = tmp_path / "encoded"
    export_samples(manifest, output, image_prefix=prefix)
    task = json.loads((output / "tasks.json").read_text())[0]
    parsed = urlsplit(task["data"]["image"])
    relative = parse_qs(parsed.query)["d"][0]
    assert not parsed.fragment
    assert (output / "images" / relative).is_file()


def test_relative_media_is_resolved_from_manifest_not_working_directory(canonical_batch, tmp_path):
    manifest, _, key = canonical_batch
    document = json.loads(manifest.read_text())
    document["media"]["uri"] = "images/source.png"
    manifest.write_text(json.dumps(document) + "\n")
    output = tmp_path / "portable"
    export_samples(manifest, output)
    task = json.loads((output / "tasks.json").read_text())[0]
    assert task["meta"]["external_id"] == key
    assert len(list((output / "images/corpus").glob("*.png"))) == 1


@pytest.mark.parametrize("prefix", ["c:/outside", "C:outside", "folder:stream"])
def test_storage_prefix_rejects_windows_drive_and_stream_syntax(canonical_batch, tmp_path, prefix):
    manifest, _, _ = canonical_batch
    output = tmp_path / "drive-prefix"
    with pytest.raises(ValueError, match="image prefix"):
        export_samples(manifest, output, image_prefix=prefix)
    assert not output.exists()


def late_metadata_png(encoded):
    import struct
    import zlib

    payload = b"tEXtprivate-coordinate\x00secret"
    chunk = struct.pack(">I", len(payload) - 4) + payload + struct.pack(">I", zlib.crc32(payload))
    return encoded[:-12] + chunk + encoded[-12:]


def test_late_png_metadata_is_rejected_after_full_decode(canonical_batch, tmp_path):
    manifest, _, _ = canonical_batch
    document = json.loads(manifest.read_text())
    image = Path(document["media"]["uri"])
    encoded = late_metadata_png(image.read_bytes())
    image.write_bytes(encoded)
    document["media"]["sha256"] = hashlib.sha256(encoded).hexdigest()
    manifest.write_text(json.dumps(document) + "\n")
    output = tmp_path / "late-metadata"
    with pytest.raises(ValueError, match="metadata-free"):
        export_samples(manifest, output)
    assert not output.exists()


@pytest.mark.parametrize("score", [float("nan"), float("inf"), float("-inf")])
@pytest.mark.parametrize("profile", ["frame", "regional"])
def test_nonfinite_results_remain_unknown_and_serialize_as_null(
    classified_batch, tmp_path, score, profile
):
    manifest, frame, proposals, regional, _ = classified_batch
    source = frame if profile == "frame" else regional
    document = json.loads(source.read_text())
    row = document["predictions"][0]
    topk = row["topk"] if profile == "frame" else row["regions"][0]["topk"]
    topk[0]["score"] = score
    if profile == "regional":
        row["regions"][0]["views"]["masked"] = topk
    source.write_text(json.dumps(document))
    output = tmp_path / "invalid-score"
    export_samples(
        manifest,
        output,
        frame_results=frame,
        proposals=proposals if profile == "regional" else None,
        regional_results=regional if profile == "regional" else None,
    )
    task = json.loads((output / "tasks.json").read_text())[0]
    prediction = task["predictions"][0]
    text = next(
        r for r in prediction["result"] if r["from_name"] in {"predicted_taxon", "region_taxon"}
    )
    assert text["value"]["text"] == ["Unknown"]
    evidence = next(r for r in prediction["result"] if r["from_name"] == "model_evidence")
    decoded = json.loads(evidence["value"]["text"][0])
    invalid = decoded["topk"] if profile == "frame" else decoded["alternatives"][0]["topk"]
    assert invalid[0]["score"] is None
    private = json.loads((output / "private/provenance.json").read_text())
    stored = (
        private["samples"][0]["frame_result"]["topk"]
        if profile == "frame"
        else (private["additional_models"]["regional"]["predictions"][0]["regions"][0]["topk"])
    )
    assert stored[0]["score"] is None
    assert "annotations" not in task


def test_nonfinite_model_metadata_is_still_refused(canonical_batch, tmp_path):
    manifest, frame, _ = canonical_batch
    document = json.loads(frame.read_text())
    document["model"]["invalid_pin"] = float("nan")
    frame.write_text(json.dumps(document))
    output = tmp_path / "invalid-pin"
    with pytest.raises(ValueError, match="JSON compliant"):
        export_samples(manifest, output, frame_results=frame)
    assert not output.exists()


def test_historical_runtime_note_is_private_and_existing_prediction_shape_is_preserved(
    canonical_batch, tmp_path
):
    manifest, frame, _ = canonical_batch
    output = tmp_path / "legacy-runtime"
    export_samples(manifest, output, frame_results=frame)
    task = json.loads((output / "tasks.json").read_text())[0]
    evidence = task["predictions"][0]["result"][-1]["value"]["text"][0]
    assert "classifier_runtime" not in json.loads(evidence)
    assert set(json.loads(evidence)) == {"interpretation", "scope", "topk", "limitations"}
    private = json.loads((output / "private/provenance.json").read_text())
    assert private["classifier_runtime"]["frame"]["status"] == "historical_unrecorded"


@pytest.mark.parametrize("invalid", [{}, [], None, False, 0, ""])
def test_explicit_frame_results_cannot_silently_disappear(canonical_batch, tmp_path, invalid):
    manifest, frame, _ = canonical_batch
    frame.write_text(json.dumps(invalid))
    output = tmp_path / "invalid-frame-document"
    with pytest.raises(ValueError, match="classifier result document"):
        export_samples(manifest, output, frame_results=frame)
    assert not output.exists()


def test_canonical_credit_is_visible_plain_text_without_source_class(canonical_batch, tmp_path):
    manifest, _, _ = canonical_batch
    document = json.loads(manifest.read_text())
    document["rights"]["attribution"] = '<Creator & friends> "authoritative"'
    manifest.write_text(json.dumps(document) + "\n")
    output = tmp_path / "visible-credit"
    export_samples(manifest, output)
    task = json.loads((output / "tasks.json").read_text())[0]
    credit = task["data"]["photo_credit"]
    assert '<Creator & friends> "authoritative"' in credit
    assert "CC-BY-4.0" in credit and "https://example.test/source" in credit
    assert "Private source class context" not in json.dumps(task)


@pytest.mark.parametrize(
    "licence, uri",
    [
        ("CC-BY-4.0", "https://creativecommons.org/licenses/by/4.0/"),
        ("cc-by-3.0", "https://creativecommons.org/licenses/by/3.0/"),
        ("CC0-1.0", "https://creativecommons.org/publicdomain/zero/1.0/"),
    ],
)
def test_explicit_licence_versions_have_canonical_links(licence, uri):
    from weedz.annotation.credits import photo_credit

    assert uri in photo_credit("Author", licence, licence, "https://example.test/source")


def test_ambiguous_historical_licence_codes_do_not_invent_versions():
    from weedz.annotation.credits import photo_credit

    text = photo_credit("Author", "cc-by", "cc0", "https://example.test/source")
    assert "creativecommons.org" not in text
    assert "[cc-by]" in text and "[cc0]" in text
