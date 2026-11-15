"""Resident SAM3 inference over canonical samples, preserving partial prompt outcomes."""

import fcntl
import hashlib
import io
import json
import os
from pathlib import Path

from PIL import Image

from weedz.segmentation.artifacts import digest, sync_directory
from weedz.segmentation.batch import (
    MAX_MANIFEST_BYTES,
    _atomic,
    _bytes,
    _durable_namespace,
    _image_bytes,
    _samples,
    _stream_rows,
)
from weedz.segmentation.regions import MAX_SOURCE_PIXELS
from weedz.segmentation.sam3_image import Sam3Image, restore_concept_regions

STATUSES = ("ok", "empty", "partial", "failed")


def _validate_image(sample, root: Path) -> bytes:
    raw = _image_bytes(sample, root)
    with Image.open(io.BytesIO(raw)) as image:
        if (
            image.size != (sample.media.width, sample.media.height)
            or image.width * image.height > MAX_SOURCE_PIXELS
        ):
            raise ValueError("Canonical source geometry differs")
        image.load()
        if image.format != "PNG" or image.mode != "RGB" or image.info or image.getexif():
            raise ValueError("Use canonical upright metadata-free RGB PNG")
    return raw


def _completed(output: Path, samples, root: Path, model: Sam3Image, identity: dict) -> dict | None:
    ready = output / "ready.json"
    if not ready.exists():
        return None
    previous = json.loads(_bytes(ready, 64_000))
    if any(previous.get(key) != value for key, value in identity.items()):
        raise ValueError("Existing SAM3 batch has different provenance")
    counts = previous.get("counts", {})
    if counts.get("partial", 1) or counts.get("failed", 1):
        return None
    encoded = _bytes(output / "proposals.jsonl", 128_000_000)
    if hashlib.sha256(encoded).hexdigest() != previous.get("proposals_sha256"):
        raise ValueError("Closed SAM3 output checksum mismatch")
    rows = [json.loads(line) for line in encoded.splitlines()]
    if len(rows) != len(samples) or previous.get("count") != len(samples):
        raise ValueError("Closed SAM3 row count differs")
    for sample, row in zip(samples, rows, strict=True):
        stage = row["segmentation"]
        if (
            row["sample_id"] != sample.id
            or row["image_sha256"] != sample.media.sha256
            or row["model_version"] != model.model_version
            or stage["status"] not in {"ok", "empty"}
            or digest(stage["provenance"]) != digest(model.metadata)
        ):
            raise ValueError("Closed SAM3 row identity differs")
        restore_concept_regions(
            _validate_image(sample, root),
            stage["regions"],
            model.config,
            expected_sha256=sample.media.sha256,
        )
    return previous


def _rows(samples, root: Path, model: Sam3Image):
    for sample in samples:
        result = model.screen((root / sample.media.uri).resolve())
        if result["source_sha256"] != sample.media.sha256:
            raise ValueError("SAM3 inference source checksum changed")
        if result["status"] not in STATUSES:
            raise ValueError("Unknown SAM3 prompt outcome")
        yield {
            "schema": 1,
            "sample_id": sample.id,
            "image_sha256": sample.media.sha256,
            "source_sample": sample.model_dump(mode="json"),
            "model_version": model.model_version,
            "segmentation": {
                **result,
                "proposal_status": result["status"],
                "view_status": "not_requested",
                "baseline_retained": False,
            },
        }


def propose_sam3_batch(
    manifest: Path,
    media_root: Path,
    output: Path,
    model: Sam3Image,
    *,
    expected_manifest_sha256: str | None = None,
) -> dict:
    raw = _bytes(manifest, MAX_MANIFEST_BYTES)
    manifest_sha = hashlib.sha256(raw).hexdigest()
    if expected_manifest_sha256 is not None and manifest_sha != expected_manifest_sha256:
        raise ValueError("Canonical manifest checksum mismatch")
    root, destination = media_root.resolve(strict=True), output.resolve()
    if any(
        destination.is_relative_to(source) or source.is_relative_to(destination)
        for source in (root, manifest.resolve().parent)
    ):
        raise ValueError("Use independent source/output namespaces")
    if any((parent / ".git").exists() for parent in (destination, *destination.parents)):
        raise ValueError("Keep canonical model outputs outside Git")
    samples = _samples(raw, root)
    for sample in samples:
        _validate_image(sample, root)
    identity = {"manifest_sha256": manifest_sha, "model_version": model.model_version}
    _durable_namespace(destination)
    with (destination / ".batch.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        previous = _completed(destination, samples, root, model, identity)
        if previous is not None:
            for name in ("proposals.jsonl", "ready.json"):
                with (destination / name).open("rb") as stream:
                    os.fsync(stream.fileno())
            _durable_namespace(destination)
            return previous
        checksum, counts = _stream_rows(
            destination / "proposals.jsonl",
            _rows(samples, root, model),
            statuses=STATUSES,
            maximum_bytes=128_000_000,
        )
        summary = {
            "schema": 1,
            **identity,
            "count": sum(counts.values()),
            "counts": counts,
            "proposals_sha256": checksum,
            "human_annotations": 0,
        }
        _atomic(destination / "ready.json", json.dumps(summary, allow_nan=False).encode())
        sync_directory(destination)
        return summary
