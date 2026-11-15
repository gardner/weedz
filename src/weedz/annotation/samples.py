"""Canonical public sample batches: no synthetic observation IDs or source-class truth."""

import hashlib
import io
import json
import shutil
from pathlib import Path
from typing import Any
from urllib.parse import quote

from PIL import Image

from weedz.annotation.auto_labels import frame_prediction, proposals_prediction
from weedz.annotation.export import _output
from weedz.annotation.label_studio import label_config
from weedz.annotation.sample_variants import add_variants, load_variants
from weedz.annotation.semantic import classifier_runtime
from weedz.annotation.serialization import NONFINITE_POLICY, result_json
from weedz.contract import Sample
from weedz.manifest import read_manifest

PUBLIC = {"cc0", "cc0-1.0", "cc-by", "cc-by-3.0", "cc-by-4.0"}


def _inputs(manifest: Path, frame_results: Path | None, proposals: Path | None) -> tuple:
    source_digest = hashlib.sha256(manifest.read_bytes()).hexdigest()
    frames = json.loads(frame_results.read_text()) if frame_results else None
    if frames and frames.get("manifest_sha256") != source_digest:
        raise ValueError("Classifier input manifest checksum mismatch")
    frame_rows = {row["external_id"]: row for row in frames["predictions"]} if frames else {}
    if frames and len(frame_rows) != len(frames["predictions"]):
        raise ValueError("Duplicate classifier asset identities")
    proposed = (
        [json.loads(line) for line in proposals.read_text().splitlines()] if proposals else []
    )
    proposal_rows = {row["sample_id"]: row for row in proposed}
    if len(proposed) != len(proposal_rows):
        raise ValueError("Duplicate proposal asset identities")
    samples = read_manifest(manifest, source_digest)
    if not 1 <= len(samples) <= 1000:
        raise ValueError("Use nonempty bounded batches, at most 1000 samples (100 recommended)")
    return source_digest, frames, frame_rows, proposal_rows, samples


def _media(sample: Sample, root: Path) -> tuple[bytes, str, tuple[int, int]]:
    if sample.rights.consent is not None or sample.rights.media_license.lower() not in PUBLIC:
        raise ValueError("Only licensed public CC0/CC BY sample batches are supported")
    if sample.rights.metadata_license.lower() not in PUBLIC:
        raise ValueError("Sample metadata licence is outside this public handoff")
    path = (root / sample.media.uri).resolve()
    if not path.is_relative_to(root):
        raise ValueError("Materialized image escapes the source batch")
    encoded = path.read_bytes()
    digest = hashlib.sha256(encoded).hexdigest()
    if digest != sample.media.sha256:
        raise ValueError("Source image checksum mismatch")
    with Image.open(io.BytesIO(encoded)) as image:
        size = image.size
        if size != (sample.media.width, sample.media.height) or size[0] * size[1] > 40_000_000:
            raise ValueError("Canonical image geometry mismatch")
        image.load()
        if image.format != "PNG" or image.mode != "RGB" or image.info or image.getexif():
            raise ValueError("Canonical media must be upright metadata-free RGB PNG")
    return encoded, digest, size


def _proposal(
    sample: Sample, digest: str, size: tuple[int, int], rows: dict, required: bool
) -> tuple:
    row = rows.get(sample.id)
    if required and row is None:
        raise ValueError("Missing proposal result for a source sample")
    if row is None:
        return None, None, ""
    if row["image_sha256"] != digest:
        raise ValueError("Proposal image checksum mismatch")
    segmentation = row["segmentation"]
    status = segmentation.get("proposal_status", segmentation["status"])
    if status not in {"ok", "empty", "failed"} or (status != "ok" and segmentation["regions"]):
        raise ValueError("Inconsistent proposal result")
    prediction = proposals_prediction(segmentation["regions"], segmentation["provenance"], size)
    state = "SAM masks unclassified" if status == "ok" else f"SAM {status}"
    return prediction, row, state


def _frame(key: str, digest: str, rows: dict, metadata: dict | None) -> tuple:
    if metadata is None:
        return None, None, ""
    row = rows.get(key)
    if row is None:
        raise ValueError("Missing classifier result for a source sample")
    if row["image_sha256"] != digest:
        raise ValueError("Classifier image checksum mismatch")
    return frame_prediction(row["topk"], metadata), row, "frame taxon proposed"


def _prepare(
    sample: Sample,
    root: Path,
    frames: dict | None,
    frame_rows: dict,
    proposal_rows: dict,
    proposals_required: bool,
    image_prefix: str,
) -> tuple:
    encoded, digest, size = _media(sample, root)
    key = hashlib.sha256(f"{sample.id}:{digest}".encode()).hexdigest()
    proposed, proposal_row, proposal_state = _proposal(
        sample, digest, size, proposal_rows, proposals_required
    )
    frame, frame_row, frame_state = _frame(
        key, digest, frame_rows, frames["model"] if frames else None
    )
    imported: dict[str, Any] = {
        "data": {
            "image": f"/data/local-files/?d={quote(f'{image_prefix}/{digest}.png')}",
            "source_dataset": sample.source,
            "pipeline_state": "; ".join(s for s in (proposal_state, frame_state) if s)
            or "Awaiting model output",
        },
        "meta": {"external_id": key, "image_sha256": digest},
    }
    predictions = [prediction for prediction in (proposed, frame) if prediction is not None]
    if predictions:
        imported["predictions"] = predictions
    portable = sample.model_copy(
        update={
            "geography": None,
            "media": sample.media.model_copy(update={"uri": f"images/{image_prefix}/{digest}.png"}),
        }
    )
    return portable, encoded, imported, frame_row, proposal_row


def _write(
    output: Path,
    prepared: list,
    frames: dict | None,
    source_digest: str,
    image_prefix: str,
    variants: dict,
) -> dict:
    output.mkdir(parents=True, exist_ok=False)
    try:
        (output / "images" / image_prefix).mkdir(parents=True)
        (output / "private").mkdir(mode=0o700)
        tasks, records = [], []
        for sample, encoded, imported, frame, proposal in prepared:
            (output / sample.media.uri).write_bytes(encoded)
            tasks.append(imported)
            records.append(
                {
                    "external_id": imported["meta"]["external_id"],
                    "sample": sample.model_dump(mode="json"),
                    "frame_result": frame,
                    "segmentation": proposal["segmentation"] if proposal else None,
                }
            )
        (output / "tasks.json").write_text(
            json.dumps(tasks, ensure_ascii=False, allow_nan=False) + "\n"
        )
        (output / "label-config.xml").write_text(label_config("assisted"))
        provenance = {
            "nonfinite_result_policy": NONFINITE_POLICY,
            "classifier_runtime": {
                "frame": classifier_runtime(frames["model"]) if frames else None,
                **{
                    name: classifier_runtime(variant.document["model"])
                    for name, variant in variants.items()
                    if variant is not None
                },
            },
            "schema_version": 1,
            "source_manifest_sha256": source_digest,
            "frame_model": frames["model"] if frames else None,
            "samples": records,
            "additional_models": {
                name: variant.document for name, variant in variants.items() if variant is not None
            },
            "interpretation": (
                "Editable predictions only; source class is context, never annotation truth"
            ),
        }
        (output / "private/provenance.json").write_text(result_json(provenance) + "\n")
        files = {
            str(path.relative_to(output)): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in sorted(output.rglob("*"))
            if path.is_file()
        }
        receipt = {
            "schema_version": 1,
            "task_count": len(tasks),
            "source_manifest_sha256": source_digest,
            "image_prefix": image_prefix,
            "files": files,
        }
        (output / "manifest.json").write_text(json.dumps(receipt, indent=2) + "\n")
        return receipt
    except BaseException:
        shutil.rmtree(output)
        raise


def export_samples(
    manifest: Path,
    output: Path,
    *,
    frame_results: Path | None = None,
    proposals: Path | None = None,
    image_prefix: str = "corpus",
    regional_results: Path | None = None,
    tiled_results: Path | None = None,
) -> dict[str, Any]:
    manifest = manifest.resolve()
    output = _output(manifest.parent, output)
    if (
        not image_prefix
        or any(p in {"", ".", ".."} for p in image_prefix.split("/"))
        or "\\" in image_prefix
        or ":" in image_prefix
    ):
        raise ValueError("Choose a relative image prefix with a storage subdirectory")
    source_digest, frames, frame_rows, proposal_rows, samples = _inputs(
        manifest, frame_results, proposals
    )
    variants = load_variants(manifest, proposals, regional_results, tiled_results)
    prepared = [
        _prepare(
            sample,
            manifest.parent,
            frames,
            frame_rows,
            proposal_rows,
            proposals is not None,
            image_prefix,
        )
        for sample in samples
    ]
    add_variants(prepared, variants)
    return _write(output, prepared, frames, source_digest, image_prefix, variants)
