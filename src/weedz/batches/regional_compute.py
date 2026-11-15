"""Masked classifier execution; legacy outputs retain their original metadata and version."""

import hashlib
import json
from pathlib import Path
from typing import Literal

from weedz.batches.compute import Computed, _existing_model
from weedz.batches.contract import artifact
from weedz.batches.profiles import ModelProfile
from weedz.batches.proposal_compute import proposal_rows
from weedz.batches.storage import ClosedBatch, read_artifact, read_owned_file
from weedz.classification.batch import _check_topk, _identity
from weedz.classification.regions import classify_region_batch


def _legacy_header(
    document: dict, batch: ClosedBatch, proposals: dict, profile: ModelProfile
) -> None:
    if (
        not isinstance(document, dict)
        or document.get("schema") != 1
        or document.get("proposals_sha256") != proposals["sha256"]
        or document.get("manifest_sha256", batch.sha256) != batch.sha256
    ):
        raise ValueError("Regional classifier source provenance mismatch")
    if not profile.matches(document["model"]):
        raise ValueError("Regional classifier artifact disagrees with its registered profile")
    version = document.get("model_version")
    if not isinstance(version, str) or not 1 <= len(version) <= 256:
        raise ValueError("Regional classifier requires its original model version")


def _legacy(
    root: Path,
    batch: ClosedBatch,
    proposals: dict,
    external: dict,
    profile: ModelProfile,
    source: list[dict],
) -> Computed:
    document = json.loads(read_artifact(root, external, 128_000_000))
    _legacy_header(document, batch, proposals, profile)
    rows = document["predictions"]
    if not isinstance(rows, list) or len(rows) != len(batch.samples):
        raise ValueError("Regional classifier prediction count differs")
    for sample, proposed, row in zip(batch.samples, source, rows, strict=True):
        expected = _identity(sample, document["model_version"])
        if any(row.get(key) != value for key, value in expected.items()):
            raise ValueError("Regional classifier asset identity mismatch")
        classified = row["regions"]
        if [r["id"] for r in classified] != [r["id"] for r in proposed["segmentation"]["regions"]]:
            raise ValueError("Regional classifier and source mask identities differ")
        for region in classified:
            _check_topk(region["topk"])
            if region["topk"] != region["views"].get("masked"):
                raise ValueError("Regional primary classification must be the declared masked view")
    return Computed(artifact(external), "external-compute")


def regions(
    root: Path,
    batch: ClosedBatch,
    proposals: dict,
    relative_output: str,
    profile: ModelProfile,
    proposer: ModelProfile,
    *,
    external: dict | None = None,
    kind: Literal["sam2", "sam3"] = "sam2",
) -> Computed:
    if profile.kind != "regions":
        raise ValueError("Choose a registered regional classifier profile")
    source = proposal_rows(root, batch, proposals, proposer, kind)
    if external is not None:
        return _legacy(root, batch, proposals, external, profile, source)
    reference = artifact({"path": relative_output, "sha256": "0" * 64})
    output = root / reference["path"]
    if not output.resolve().is_relative_to(root.resolve()) or output.resolve().is_relative_to(
        batch.manifest.parent
    ):
        raise ValueError("Regional output must use an independent owned namespace")
    if output.exists():
        reference["sha256"] = hashlib.sha256(read_owned_file(output, root, 128_000_000)).hexdigest()
        model = _existing_model(root, reference, profile)
        origin = "activity-cache"
    else:
        model = profile.load()
        origin = "temporal-activity"
    result = classify_region_batch(
        batch.manifest,
        batch.manifest.parent,
        root / artifact(proposals)["path"],
        output,
        model,
        kind,
    )
    if (
        result["manifest_sha256"] != batch.sha256
        or result["proposals_sha256"] != proposals["sha256"]
    ):
        raise ValueError("Regional classifier inputs changed during execution")
    reference["sha256"] = hashlib.sha256(read_owned_file(output, root, 128_000_000)).hexdigest()
    return Computed(reference, origin)
