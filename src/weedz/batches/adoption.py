"""Explicit legacy adoption profiles cannot fall back to fresh model inference."""

import json
from pathlib import Path
from typing import Literal, cast

from weedz.batches.activities import BatchRegistry
from weedz.batches.compute import classify
from weedz.batches.contract import batch_request
from weedz.batches.profiles import Kind, ModelProfile
from weedz.batches.proposal_compute import proposal_rows
from weedz.batches.regional_compute import regions
from weedz.batches.storage import read_artifact, validate_closed_batch


def _no_inference():
    raise RuntimeError("A cache-only adoption profile cannot execute inference")


def adoption_registry(config: dict) -> BatchRegistry:
    kind = config["proposer_kind"]
    if kind not in {"sam2", "sam3"}:
        raise ValueError("Unknown legacy proposer kind")
    metadata = config["metadata"]
    segmentation, classifier = config["segmentation_profile"], config["classifier_profile"]
    return BatchRegistry(
        {
            segmentation: ModelProfile(
                segmentation, "proposals", metadata["proposals"], _no_inference
            )
        },
        {
            classifier: {
                name: ModelProfile(classifier, cast(Kind, name), value, _no_inference)
                for name, value in metadata.items()
                if name != "proposals"
            }
        },
        {segmentation: cast(Literal["sam2", "sam3"], kind)},
    )


def prepare_adoption(root: Path, value: dict, *, proposer_kind: str = "sam2") -> dict:
    request = batch_request(value)
    if set(request["cached"]) != {"proposals", *request["variants"]}:
        raise ValueError("Cache-only adoption requires every requested model artifact")
    root = root.resolve()
    batch = validate_closed_batch(root, request["manifest"], request["ready"])
    proposal_ref = request["cached"]["proposals"]
    proposal_data = read_artifact(root, proposal_ref, 128_000_000)
    try:
        first = json.loads(proposal_data.splitlines()[0])
        metadata = {"proposals": first["segmentation"]["provenance"]}
        for variant in request["variants"]:
            document = json.loads(read_artifact(root, request["cached"][variant], 128_000_000))
            metadata[variant] = document["model"]
    except (IndexError, KeyError, TypeError) as error:
        raise ValueError("Legacy artifacts lack their original model metadata") from error
    config = {
        "schema": 1,
        "artifact_root": str(root),
        "cache_only": True,
        "proposer_kind": proposer_kind,
        "segmentation_profile": request["segmentation_profile"],
        "classifier_profile": request["classifier_profile"],
        "metadata": metadata,
    }
    registry = adoption_registry(config)
    registry.pins(request)
    sam = registry.segmentation[request["segmentation_profile"]]
    kind = cast(Literal["sam2", "sam3"], proposer_kind)
    proposal_rows(root, batch, proposal_ref, sam, kind)
    for variant in request["variants"]:
        profile = registry.classifiers[request["classifier_profile"]][variant]
        if variant == "regions":
            regions(
                root,
                batch,
                proposal_ref,
                "unused-adoption.json",
                profile,
                sam,
                external=request["cached"][variant],
                kind=kind,
            )
        else:
            classify(
                root, batch, "unused-adoption.json", profile, external=request["cached"][variant]
            )
    return config
