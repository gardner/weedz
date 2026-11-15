"""Canonical native-margin activity adapter; no probability conversion or SAM inference."""

import hashlib
import json
from pathlib import Path
from typing import Any, Literal, cast

from weedz.batches.compute import Computed
from weedz.batches.contract import artifact
from weedz.batches.profiles import ModelProfile
from weedz.batches.storage import ClosedBatch, read_artifact, read_owned_file
from weedz.classification.bioclip_batches import classify_margin_batch


class MetadataOnly:
    def __init__(self, metadata: dict) -> None:
        self.metadata = metadata

    def profile_metadata(self, scope, proposer=None):
        return self.metadata


def _model(
    root: Path, output: Path, external: dict | None, reference: dict, profile: ModelProfile
) -> tuple[Any, Literal["external-compute", "activity-cache", "temporal-activity"]]:
    if output.exists():
        if external is None:
            reference["sha256"] = hashlib.sha256(
                read_owned_file(output, root, 128_000_000)
            ).hexdigest()
        document = json.loads(read_artifact(root, reference, 128_000_000))
        if not profile.matches(document["model"]):
            raise ValueError("BioCLIP cached profile disagrees")
        return MetadataOnly(document["model"]), "external-compute" if external else "activity-cache"
    else:
        if external is not None:
            raise ValueError("Missing pinned BioCLIP artifact")
        return profile.load(), "temporal-activity"


def run(
    root: Path,
    batch: ClosedBatch,
    relative: str,
    profile: ModelProfile,
    *,
    external: dict | None = None,
    proposals: dict | None = None,
    proposer: ModelProfile | None = None,
    kind: Literal["sam2", "sam3"] = "sam2",
) -> Computed:
    from weedz.batches.proposal_compute import proposal_rows

    if profile.kind not in {"frame", "regions"}:
        raise ValueError("BioCLIP does not expose a tiles variant")
    if proposals is not None:
        if proposer is None:
            raise ValueError("Missing registered SAM proposal profile")
        proposal_rows(root, batch, proposals, proposer, kind)
    reference = artifact(external or {"path": relative, "sha256": "0" * 64})
    output = root / reference["path"]
    if output.resolve().is_relative_to(
        batch.manifest.parent
    ) or not output.resolve().is_relative_to(root.resolve()):
        raise ValueError("BioCLIP output must use an independent owned namespace")
    model, origin = _model(root, output, external, reference, profile)
    result = classify_margin_batch(
        batch.manifest,
        batch.manifest.parent,
        output,
        model,
        cast(Literal["frame", "regions"], profile.kind),
        proposals=root / proposals["path"] if proposals else None,
        proposer_kind=kind,
        expected_manifest_sha256=batch.sha256,
        expected_proposals_sha256=proposals["sha256"] if proposals else None,
        verified_existing_sha256=reference["sha256"] if output.exists() else None,
    )
    if not profile.matches(result["model"]):
        raise ValueError("Computed BioCLIP profile disagrees")
    if origin != "temporal-activity":
        read_artifact(root, reference, 128_000_000)
        return Computed(reference, origin)
    reference["sha256"] = hashlib.sha256(read_owned_file(output, root, 128_000_000)).hexdigest()
    return Computed(reference, origin)
