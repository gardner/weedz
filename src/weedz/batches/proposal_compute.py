"""Canonical SAM computation and exact completed-output adoption without inference."""

import hashlib
import json
from pathlib import Path
from typing import Literal

from weedz.batches.compute import Computed
from weedz.batches.contract import artifact
from weedz.batches.profiles import ModelProfile
from weedz.batches.storage import ClosedBatch, read_artifact, read_owned_file
from weedz.classification.batch import _snapshot
from weedz.classification.regions import _inputs, _restore
from weedz.contract import Sample
from weedz.segmentation.batch import propose_batch
from weedz.segmentation.regions import ProposalConfig
from weedz.segmentation.sam3_batch import propose_sam3_batch


def proposal_rows(
    root: Path,
    batch: ClosedBatch,
    reference: dict,
    profile: ModelProfile,
    kind: Literal["sam2", "sam3"] = "sam2",
) -> list[dict]:
    encoded = read_artifact(root, reference, 128_000_000)
    samples, rows = _inputs(batch.manifest, batch.sha256, encoded, batch.manifest.parent)
    versions = set()
    for sample, row in zip(samples, rows, strict=True):
        stage = row["segmentation"]
        if not profile.matches(stage["provenance"]):
            raise ValueError("Proposal artifact disagrees with its registered profile")
        if "source_sample" in row and Sample.model_validate(row["source_sample"]) != sample:
            raise ValueError("Proposal source sample differs from the closed manifest")
        versions.add(row.get("model_version"))
        records = stage["regions"]
        if len({r["id"] for r in records}) != len(records):
            raise ValueError("Duplicate proposal region identities")
        encoded_image = _snapshot(sample, batch.manifest.parent)
        if sample.media.sha256 is None:
            raise ValueError("Canonical source lacks its image checksum")
        _restore(encoded_image, sample.media.sha256, stage, kind)
    if len(versions) != 1 or None in versions:
        raise ValueError("Proposal model versions disagree within the batch")
    return rows


def _reference(root: Path, path: Path) -> dict[str, str]:
    encoded = read_owned_file(path, root, 128_000_000)
    return artifact(
        {"path": str(path.relative_to(root)), "sha256": hashlib.sha256(encoded).hexdigest()}
    )


def _cached(
    root: Path,
    batch: ClosedBatch,
    directory: Path,
    profile: ModelProfile,
    kind: Literal["sam2", "sam3"],
) -> dict | None:
    if not (directory / "ready.json").exists():
        return None
    ready = json.loads(read_owned_file(directory / "ready.json", root, 64_000))
    if ready.get("manifest_sha256") != batch.sha256:
        raise ValueError("Existing proposal readiness belongs to another manifest")
    if ready.get("counts", {}).get("failed", 1) != 0 or ready.get("counts", {}).get("partial", 0):
        return None
    reference = _reference(root, directory / "proposals.jsonl")
    if ready.get("proposals_sha256") != reference["sha256"]:
        raise ValueError("Proposal readiness checksum differs from its output")
    rows = proposal_rows(root, batch, reference, profile, kind)
    if ready.get("count") != len(rows):
        raise ValueError("Proposal readiness count differs")
    return reference


def segment(
    root: Path,
    batch: ClosedBatch,
    relative_output: str,
    profile: ModelProfile,
    *,
    external: dict[str, str] | None = None,
    kind: Literal["sam2", "sam3"] = "sam2",
) -> Computed:
    if profile.kind != "proposals":
        raise ValueError("Choose a registered proposal model profile")
    if external is not None:
        reference = artifact(external)
        proposal_rows(root, batch, reference, profile, kind)
        return Computed(reference, "external-compute")
    pinned = artifact({"path": relative_output, "sha256": "0" * 64})
    directory = root / pinned["path"]
    if not directory.resolve().is_relative_to(root.resolve()) or directory.resolve().is_relative_to(
        batch.manifest.parent
    ):
        raise ValueError("Proposal output must use an independent owned namespace")
    previous = _cached(root, batch, directory, profile, kind)
    if previous is not None:
        return Computed(previous, "activity-cache")
    model = profile.load()
    if kind == "sam3":
        summary = propose_sam3_batch(
            batch.manifest,
            batch.manifest.parent,
            directory,
            model,
            expected_manifest_sha256=batch.sha256,
        )
    else:
        summary = propose_batch(
            batch.manifest,
            batch.manifest.parent,
            directory,
            model,
            expected_manifest_sha256=batch.sha256,
            config=ProposalConfig(**profile.metadata["proposal_config"]),
        )
    if summary["counts"]["failed"] or summary["counts"].get("partial", 0):
        raise RuntimeError("Some proposal work failed; completed samples remain resumable")
    reference = _reference(root, directory / "proposals.jsonl")
    proposal_rows(root, batch, reference, profile, kind)
    return Computed(reference, "temporal-activity")
