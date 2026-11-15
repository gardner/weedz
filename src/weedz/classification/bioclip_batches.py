"""Bounded resumable native cosine/margin batches, separate from softmax classifiers."""

import fcntl
import hashlib
import json
from pathlib import Path
from typing import Any, Literal

from weedz.batches.receipts import seal_file
from weedz.classification.batch import (
    MAX_RESULT_BYTES,
    _encoded_result,
    _identity,
    _snapshot,
    _verified_result,
)
from weedz.classification.bioclip import validate_frame_geometry, validate_scores
from weedz.classification.regions import _inputs, _restored_photo
from weedz.discovery.inference import file_sha256
from weedz.manifest import read_manifest, write_atomic
from weedz.segmentation.artifacts import digest, durable_mkdir

Scope = Literal["frame", "regions"]


def _sources(manifest, root, proposals, scope, kind, expected_manifest, expected_proposals):
    manifest_sha = file_sha256(manifest)
    if expected_manifest is not None and manifest_sha != expected_manifest:
        raise ValueError("BioCLIP manifest differs from pinned input")
    samples = read_manifest(manifest, manifest_sha)
    if not 1 <= len(samples) <= 1000:
        raise ValueError("Use a bounded batch of1–1000 samples")
    for sample in samples:
        _snapshot(sample, root)
    rows = []
    proposal_sha = None
    if scope == "regions":
        samples, rows, proposal_sha = _proposal_sources(
            manifest, manifest_sha, root, proposals, kind, expected_proposals
        )
    if file_sha256(manifest) != manifest_sha:
        raise ValueError("Manifest changed during read")
    return samples, rows, manifest_sha, proposal_sha


def _proposal_sources(manifest, manifest_sha, root, proposals, kind, expected_proposals):
    if proposals is None:
        raise ValueError("BioCLIP regions require source proposals")
    with proposals.open("rb") as stream:
        encoded = stream.read(128_000_001)
    if len(encoded) > 128_000_000:
        raise ValueError("Proposal batch exceeds cap")
    proposal_sha = hashlib.sha256(encoded).hexdigest()
    if expected_proposals is not None and proposal_sha != expected_proposals:
        raise ValueError("BioCLIP proposals differ from pinned input")
    samples, rows = _inputs(manifest, manifest_sha, encoded, root)
    for sample, row in zip(samples, rows, strict=True):
        _restored_photo(sample, row, root, kind)
    if len({digest(row["segmentation"]["provenance"]) for row in rows}) != 1:
        raise ValueError("Mixed proposal model provenance")
    return samples, rows, proposal_sha


def validate_region(region: dict) -> None:
    if set(region.get("views", {})) != {"tight", "masked", "context"}:
        raise ValueError("BioCLIP requires all three crop views")
    for summary in region["views"].values():
        validate_scores(summary, frame=False)


def _validate_row(row, sample, version, scope, proposed, root):
    expected = _identity(sample, version)
    if any(row.get(k) != v for k, v in expected.items()):
        raise ValueError("BioCLIP source identity differs")
    if scope == "frame":
        validate_frame_geometry(
            row["scores"], (sample.media.width, sample.media.height), _snapshot(sample, root)
        )
        validate_scores(row["scores"], frame=True)
    else:
        ids = [r["id"] for r in proposed["segmentation"]["regions"]]
        if [r["id"] for r in row["regions"]] != ids:
            raise ValueError("BioCLIP region identities differ")
        for region in row["regions"]:
            validate_region(region)


def _read_pinned_result(output: Path, verified: str | None) -> dict:
    # The caller SHA and the internal digest must describe these same captured bytes.
    with output.open("rb") as stream:
        encoded = stream.read(MAX_RESULT_BYTES + 1)
    if len(encoded) > MAX_RESULT_BYTES:
        raise ValueError("BioCLIP result exceeds byte cap")
    if verified is not None and hashlib.sha256(encoded).hexdigest() != verified:
        raise ValueError("External BioCLIP artifact checksum changed")
    result = json.loads(encoded)
    if not isinstance(result, dict):
        raise ValueError("Invalid BioCLIP result document")
    body = {key: value for key, value in result.items() if key != "result_sha256"}
    if result.get("result_sha256") != digest(body):
        raise ValueError("BioCLIP result checksum mismatch")
    return result


def _cached(output, header, samples, proposed, scope, verified, root):
    result = _read_pinned_result(output, verified)
    if any(digest({k: result.get(k)}) != digest({k: v}) for k, v in header.items()):
        raise ValueError("Existing BioCLIP batch has different provenance")
    rows = result.get("predictions")
    if not isinstance(rows, list) or len(rows) != len(samples):
        raise ValueError("Incomplete BioCLIP rows")
    for index, (sample, row) in enumerate(zip(samples, rows, strict=True)):
        _validate_row(
            row, sample, header["model_version"], scope, proposed[index] if proposed else None, root
        )
    seal_file(output.parent, output)
    return result


def _predict_photo(sample, root, model, scope, proposed, kind, version):
    row = _identity(sample, version)
    if scope == "frame":
        row["scores"] = model.frame(_snapshot(sample, root))
    else:
        regions, ids = _restored_photo(sample, proposed, root, kind)
        row["regions"] = [
            {"id": identifier, "views": model.regions(region.views)}
            for identifier, region in zip(ids, regions, strict=True)
        ]
    _validate_row(row, sample, version, scope, proposed, root)
    return row


def _part(output, header, sample, root, model, scope, proposed, kind):
    # Individual completed photos survive an activity interruption; failures are not cached.
    stamp = digest({"header": header, "sample": sample.model_dump(mode="json")})
    path = output.parent / (output.name + ".parts") / (stamp + ".json")
    durable_mkdir(path.parent)
    with path.with_suffix(".lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if path.exists():
            record = _verified_result(path, None)
            seal_file(output.parent, path)
            row = record["prediction"]
            if record["input_sha256"] != stamp:
                raise ValueError("BioCLIP partial input identity differs")
            _validate_row(row, sample, header["model_version"], scope, proposed, root)
            return row
        row = _predict_photo(sample, root, model, scope, proposed, kind, header["model_version"])
        proposer = proposed["segmentation"]["provenance"] if proposed else None
        if digest(model.profile_metadata(scope, proposer)) != digest(header["model"]):
            raise ValueError("BioCLIP model metadata changed during photo inference")
        body = {"input_sha256": stamp, "prediction": row}
        write_atomic(path, _encoded_result({**body, "result_sha256": digest(body)}))
        seal_file(output.parent, path)
        return row


def classify_margin_batch(
    manifest: Path,
    media_root: Path,
    output: Path,
    model: Any,
    scope: Scope = "frame",
    *,
    proposals: Path | None = None,
    proposer_kind: Literal["sam2", "sam3"] = "sam2",
    expected_manifest_sha256: str | None = None,
    expected_proposals_sha256: str | None = None,
    verified_existing_sha256: str | None = None,
) -> dict:
    if scope not in {"frame", "regions"}:
        raise ValueError("BioCLIP supports frame and regions only")
    samples, proposed, manifest_sha, proposal_sha = _sources(
        manifest,
        media_root,
        proposals,
        scope,
        proposer_kind,
        expected_manifest_sha256,
        expected_proposals_sha256,
    )
    proposer = proposed[0]["segmentation"]["provenance"] if proposed else None
    metadata = model.profile_metadata(scope, proposer)
    header = {
        "schema": 1,
        "model": metadata,
        "model_version": f"BioCLIP GPU {scope} margins · {digest(metadata)[:12]}",
        "manifest_sha256": manifest_sha,
    }
    if proposals is not None:
        header["proposals_sha256"] = proposal_sha
    if output.exists():
        return _cached(
            output, header, samples, proposed, scope, verified_existing_sha256, media_root
        )
    rows = [
        _part(
            output,
            header,
            sample,
            media_root,
            model,
            scope,
            proposed[i] if proposed else None,
            proposer_kind,
        )
        for i, sample in enumerate(samples)
    ]
    if digest(model.profile_metadata(scope, proposer)) != digest(metadata):
        raise ValueError("BioCLIP model metadata changed during inference")
    if file_sha256(manifest) != manifest_sha:
        raise ValueError("BioCLIP manifest changed during inference")
    if proposals is not None and file_sha256(proposals) != proposal_sha:
        raise ValueError("BioCLIP proposals changed during inference")
    body = {**header, "predictions": rows}
    result = {**body, "result_sha256": digest(body)}
    with output.with_suffix(".lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if output.exists():
            return _cached(
                output, header, samples, proposed, scope, verified_existing_sha256, media_root
            )
        write_atomic(output, _encoded_result(result))
        seal_file(output.parent, output)
    return result
