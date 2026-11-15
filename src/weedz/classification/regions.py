"""Species proposals on verified SAM masks; masked pixels are the fixed primary view."""

import fcntl
import io
import json
from pathlib import Path
from typing import Literal

from PIL import Image

from weedz.classification.batch import (
    Classifier,
    _check_topk,
    _identity,
    _snapshot,
    _verified_result,
)
from weedz.contract import Sample
from weedz.discovery.inference import file_sha256
from weedz.manifest import read_manifest, write_atomic
from weedz.segmentation.artifacts import digest
from weedz.segmentation.sam3_image import Sam3Config, restore_concept_region
from weedz.segmentation.stages import restored_regions

Proposer = Literal["sam2", "sam3"]


def _inputs(manifest: Path, source: Path, root: Path) -> tuple[list[Sample], list[dict]]:
    samples = read_manifest(manifest, file_sha256(manifest))
    if not 1 <= len(samples) <= 1000:
        raise ValueError("Use a nonempty batch of at most 1000 samples")
    if source.stat().st_size > 128_000_000:
        raise ValueError("Proposal batch exceeds the resource cap")
    rows = [json.loads(line) for line in source.read_text().splitlines() if line.strip()]
    if len(rows) != len(samples):
        raise ValueError("Incomplete proposal rows")
    for sample, row in zip(samples, rows, strict=True):
        _snapshot(sample, root)
        if row.get("sample_id") != sample.id or row.get("image_sha256") != sample.media.sha256:
            raise ValueError("Proposal asset provenance mismatch")
        stage = row["segmentation"]
        if stage["status"] not in {"ok", "empty"}:
            raise ValueError("Classification requires completed segmentation")
        if bool(stage["regions"]) != (stage["status"] == "ok"):
            raise ValueError("Segmentation status and regions disagree")
    return samples, rows


def _restore(image: Image.Image, stage: dict, proposer: Proposer) -> list:
    records = stage["regions"]
    if proposer == "sam2":
        return restored_regions(
            image, [{k: v for k, v in r.items() if k != "views"} for r in records]
        )
    config = Sam3Config(**stage["provenance"]["config"])
    if len(records) > config.max_regions * len(config.prompts):
        raise ValueError("SAM3 region budget exceeded")
    if any(record["prompt"] not in config.prompts for record in records):
        raise ValueError("SAM3 prompt disagrees with declared profile")
    return [restore_concept_region(image, record, config) for record in records]


def _cached(
    output: Path, header: dict, samples: list[Sample], proposed: list[dict], sha: str | None
):
    result = _verified_result(output, sha)
    if any(digest({key: result.get(key)}) != digest({key: value}) for key, value in header.items()):
        raise ValueError("Existing regional batch has different provenance")
    rows = result.get("predictions")
    if not isinstance(rows, list) or len(rows) != len(samples):
        raise ValueError("Incomplete regional prediction rows")
    for sample, source, row in zip(samples, proposed, rows, strict=True):
        expected = _identity(sample, header["model_version"])
        if any(row.get(key) != value for key, value in expected.items()):
            raise ValueError("Cached regional asset identity mismatch")
        regions = row["regions"]
        if [r["id"] for r in regions] != [r["id"] for r in source["segmentation"]["regions"]]:
            raise ValueError("Cached region identities differ")
        for region in regions:
            _check_topk(region["topk"])
            if region["topk"] != region["views"].get("masked"):
                raise ValueError("Cached primary classifier view changed")
    return result


def _predict(samples, rows, root, model, proposer, version):
    result = []
    for sample, row in zip(samples, rows, strict=True):
        with Image.open(io.BytesIO(_snapshot(sample, root))) as original:
            image = original.convert("RGB")
        stage = row["segmentation"]
        regions = _restore(image, stage, proposer)
        ids = [record["id"] for record in stage["regions"]]
        if len(set(ids)) != len(ids):
            raise ValueError("Duplicate region identities")
        classified = []
        for start in range(0, len(regions), 32):
            part = regions[start : start + 32]
            alternatives = model.predict([region.views["masked"] for region in part])
            for region_id, topk in zip(ids[start : start + 32], alternatives, strict=True):
                _check_topk(topk)
                classified.append({"id": region_id, "topk": topk, "views": {"masked": topk}})
        result.append({**_identity(sample, version), "regions": classified})
    return result


def classify_region_batch(
    manifest: Path,
    media_root: Path,
    proposals: Path,
    output: Path,
    model: Classifier,
    proposer: Proposer = "sam2",
    *,
    verified_existing_sha256: str | None = None,
) -> dict:
    """Classify closed JSONL proposals, preserving source and mask identities on retries."""
    if proposer not in {"sam2", "sam3"}:
        raise ValueError("Unknown region proposer")
    # Snapshot the closed input before parsing; reject concurrent replacement of that reference.
    source_sha, manifest_sha = file_sha256(proposals), file_sha256(manifest)
    samples, rows = _inputs(manifest, proposals, media_root)
    if file_sha256(proposals) != source_sha or file_sha256(manifest) != manifest_sha:
        raise ValueError("Input provenance changed while reading")
    provenance = rows[0]["segmentation"]["provenance"]
    if any(digest(row["segmentation"]["provenance"]) != digest(provenance) for row in rows):
        raise ValueError("Proposal model provenance differs within the batch")
    metadata = {
        **model.metadata,
        "input_policy": "Actual SAM masked crop only; source taxonomy not supplied",
        "proposer": provenance,
        "proposer_kind": proposer,
        "primary_view": "masked",
        "crop_geometry_revision": 1,
    }
    version = f"{proposer.upper()} + PlantCLEF masked · {digest(metadata)[:12]}"
    header = {
        "schema": 1,
        "model": metadata,
        "model_version": version,
        "manifest_sha256": manifest_sha,
        "proposals_sha256": source_sha,
    }
    if output.exists():
        return _cached(output, header, samples, rows, verified_existing_sha256)
    predicted = _predict(samples, rows, media_root, model, proposer, version)
    body = {**header, "predictions": predicted}
    result = {**body, "result_sha256": digest(body)}
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.with_suffix(output.suffix + ".lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if output.exists():
            return _cached(output, header, samples, rows, verified_existing_sha256)
        write_atomic(output, (json.dumps(result, indent=2, allow_nan=False) + "\n").encode())
    return result
