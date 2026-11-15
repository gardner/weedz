"""Closed canonical-Sample proposal batches; injected models never start inside this API."""

import fcntl
import hashlib
import io
import json
import os
import tempfile
import time
from dataclasses import asdict
from pathlib import Path
from typing import Any

from PIL import Image, ImageOps

from weedz.contract import Sample, require_task
from weedz.segmentation.artifacts import StageArtifacts, digest
from weedz.segmentation.pipeline import Proposer
from weedz.segmentation.regions import (
    MAX_SOURCE_BYTES,
    MAX_SOURCE_PIXELS,
    ProposalConfig,
    proposals,
)

MAX_MANIFEST_BYTES = 32_000_000
MAX_BATCH_SAMPLES = 1000
DEFAULT_CONFIG = ProposalConfig()


def _bytes(path: Path, limit: int) -> bytes:
    with path.open("rb") as stream:
        raw = stream.read(limit + 1)
    if len(raw) > limit:
        raise ValueError("Batch input exceeds resource cap")
    return raw


def _image_bytes(sample: Sample, media_root: Path) -> bytes:
    path = Path(sample.media.uri).resolve(strict=True)
    if not path.is_relative_to(media_root):
        raise ValueError("Sample image escapes media root")
    raw = _bytes(path, MAX_SOURCE_BYTES)
    if sample.media.sha256 is None or hashlib.sha256(raw).hexdigest() != sample.media.sha256:
        raise ValueError("Sample image checksum mismatch")
    return raw


def _samples(raw: bytes, media_root: Path) -> list[Sample]:
    lines = raw.splitlines()
    if not 1 <= len(lines) <= MAX_BATCH_SAMPLES:
        raise ValueError("Batch must contain 1–1000 samples")
    samples = [require_task(Sample.model_validate_json(line), "inference") for line in lines]
    if len({sample.id for sample in samples}) != len(samples):
        raise ValueError("Duplicate canonical sample ID")
    for sample in samples:
        _image_bytes(sample, media_root)
    return samples


def _image(sample: Sample, media_root: Path) -> Image.Image:
    # Hash and decode the SAME bytes: a concurrent replacement cannot inherit attribution.
    with Image.open(io.BytesIO(_image_bytes(sample, media_root))) as image:
        if image.width * image.height > MAX_SOURCE_PIXELS:
            raise ValueError("Sample image exceeds pixel cap")
        upright = ImageOps.exif_transpose(image).convert("RGB")
    if (sample.media.width, sample.media.height) != upright.size:
        raise ValueError("Sample dimensions differ from upright pixels")
    return upright


def _atomic(path: Path, raw: bytes) -> None:
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as stream:
        temporary = Path(stream.name)
        try:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
            os.replace(temporary, path)
        finally:
            temporary.unlink(missing_ok=True)


def _result(sample: Sample, root: Path, proposer: Proposer, config: ProposalConfig) -> dict:
    start = time.monotonic()
    try:
        image = _image(sample, root)
        regions = proposals(image, proposer.generate(image), config)
        result = {
            "status": "ok" if regions else "empty",
            "regions": [{**region.record(), "views": {}} for region in regions],
        }
    except (ValueError, RuntimeError, OSError, MemoryError) as error:
        result = {"status": "failed", "failure_type": type(error).__name__, "regions": []}
    return {**result, "elapsed_seconds": time.monotonic() - start}


def _rows(
    samples: list[Sample],
    root: Path,
    output: Path,
    proposer: Proposer,
    config: ProposalConfig,
    version: str,
) -> list[dict]:
    artifacts = StageArtifacts(output, "real-sam-proposals")
    rows = []
    for sample in samples:
        inputs = {"image_sha256": sample.media.sha256, "model_version": version}
        result = artifacts.read("proposals", sample.id, inputs)
        if result is None or result["status"] == "failed":
            result = artifacts.write(
                "proposals", sample.id, inputs, _result(sample, root, proposer, config)
            )
        rows.append(
            {
                "schema": 1,
                "sample_id": sample.id,
                "image_sha256": sample.media.sha256,
                "source_sample": sample.model_dump(mode="json"),
                "model_version": version,
                "segmentation": {
                    "schema": 1,
                    "baseline_retained": False,
                    "proposal_status": result["status"],
                    "view_status": "not_requested",
                    "provenance": proposer.metadata,
                    **result,
                },
            }
        )
    return rows


def _publish(
    samples: list[Sample],
    root: Path,
    output: Path,
    proposer: Proposer,
    config: ProposalConfig,
    manifest_sha: str,
) -> dict[str, Any]:
    version = "sam2.1-tiny-proposals-batch-v1:" + digest(
        {
            "provenance": proposer.metadata,
            "configuration": asdict(config),
            "schema": 1,
        }
    )
    identity = {"manifest_sha256": manifest_sha, "model_version": version}
    ready = output / "ready.json"
    if ready.exists():
        previous = json.loads(ready.read_text())
        if any(previous.get(key) != value for key, value in identity.items()):
            raise ValueError("Closed batch provenance changed; use a new output namespace")
    rows = _rows(samples, root, output, proposer, config, version)
    raw = "".join(json.dumps(row, allow_nan=False) + "\n" for row in rows).encode()
    counts = {
        status: sum(row["segmentation"]["status"] == status for row in rows)
        for status in ("ok", "empty", "failed")
    }
    summary = {
        "schema": 1,
        **identity,
        "count": len(rows),
        "counts": counts,
        "proposals_sha256": hashlib.sha256(raw).hexdigest(),
        "human_annotations": 0,
    }
    _atomic(output / "proposals.jsonl", raw)
    _atomic(ready, json.dumps(summary, allow_nan=False).encode())
    return summary


def propose_batch(
    manifest: Path,
    media_root: Path,
    output: Path,
    proposer: Proposer,
    *,
    expected_manifest_sha256: str | None = None,
    config: ProposalConfig = DEFAULT_CONFIG,
) -> dict[str, Any]:
    """Resume exact-image/config proposal work, then publish data before its ready marker.

    Failed photos remain explicit and retryable. Completed per-sample evidence is canonical;
    this function does not classify, change source annotations, or publish to Label Studio.
    The caller owns GPU scheduling, model preflight, and retry policy for partial batches.
    """
    raw = _bytes(manifest, MAX_MANIFEST_BYTES)
    manifest_sha = hashlib.sha256(raw).hexdigest()
    if expected_manifest_sha256 is not None and expected_manifest_sha256 != manifest_sha:
        raise ValueError("Batch manifest checksum mismatch")
    root = media_root.resolve(strict=True)
    samples = _samples(raw, root)
    output.mkdir(parents=True, exist_ok=True)
    with (output / ".batch.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        return _publish(samples, root, output, proposer, config, manifest_sha)
