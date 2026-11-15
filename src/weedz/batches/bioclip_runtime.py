"""Reusable registered GPU BioCLIP margin profiles, with cached-only SAM evidence."""

import json
from functools import cache
from pathlib import Path

from weedz.batches.activities import BatchRegistry
from weedz.batches.profiles import ModelProfile, sam_identity
from weedz.batches.storage import read_artifact
from weedz.classification.bioclip import KIND, BioClipClassifier, identity
from weedz.segmentation.artifacts import digest


class Registry(BatchRegistry):
    def pins(self, request):
        if not set(request["variants"]).issubset({"frame", "regions"}):
            raise ValueError("BioCLIP supports frame and regions only")
        if not request["cached"].get("proposals"):
            raise ValueError("Supply verified cached SAM proposals; BioCLIP workers never run SAM")
        return super().pins(request)


def _no_sam():
    raise RuntimeError("BioCLIP classifier workers never run SAM")


class View:
    def __init__(self, model, scope, proposer):
        self.model = model
        self.metadata = model.profile_metadata(scope, proposer)

    def profile_metadata(self, scope, proposer=None):
        return self.model.profile_metadata(scope, proposer)

    def frame(self, encoded):
        return self.model.frame(encoded)

    def regions(self, views):
        return self.model.regions(views)


def registry_from_bioclip_config(config: dict) -> BatchRegistry:
    if config.get("classifier_kind") != KIND or config.get("device") != "cuda:0":
        raise ValueError("Choose the explicit GPU BioCLIP margin profile")
    if config.get("cache_only"):
        raise ValueError("BioCLIP GPU registry is not cache-only adoption")
    metadata = config["metadata"]
    proposer = metadata["proposals"]
    sam_identity(proposer)
    kind = "sam3" if proposer.get("profile") == "sam3-image-concept-v1" else "sam2"
    if config.get("proposer_kind") != kind:
        raise ValueError("Cached SAM kind disagrees")
    for scope in ("frame", "regions"):
        identity(metadata[scope], scope)
    if digest(sam_identity(metadata["regions"]["proposer"])) != digest(sam_identity(proposer)):
        raise ValueError("BioCLIP regional proposer differs from registered SAM")

    @cache
    def load():
        return BioClipClassifier.load(Path(config["embedding_cache"]), config["model_key"])

    group = config["classifier_profile"]
    sam = config["segmentation_profile"]
    return Registry(
        {sam: ModelProfile(sam, "proposals", proposer, _no_sam)},
        {
            group: {
                scope: ModelProfile(
                    group,
                    scope,
                    metadata[scope],
                    lambda scope=scope: View(load(), scope, proposer),
                    identity=identity,
                )
                for scope in ("frame", "regions")
            }
        },
        {sam: kind},
    )


def prepare_bioclip_config(root: Path, proposals: dict, model_key: str = "bioclip-2") -> dict:
    encoded = read_artifact(root.resolve(), proposals, 128_000_000)
    rows = [json.loads(line) for line in encoded.splitlines()]
    if not 1 <= len(rows) <= 1000:
        raise ValueError("Use a bounded completed proposal batch")
    proposer = rows[0]["segmentation"]["provenance"]
    sam_identity(proposer)
    if any(row["segmentation"]["provenance"] != proposer for row in rows):
        raise ValueError("Mixed SAM profiles")
    kind = "sam3" if proposer.get("profile") == "sam3-image-concept-v1" else "sam2"
    cache_dir = root.resolve() / "embeddings"
    model = BioClipClassifier.load(cache_dir, model_key)
    config = {
        "schema": 1,
        "artifact_root": str(root.resolve()),
        "classifier_kind": KIND,
        "device": "cuda:0",
        "model_key": model_key,
        "embedding_cache": str(cache_dir),
        "classifier_profile": "bioclip-margins-v1",
        "segmentation_profile": "sam3-image-concept-v1" if kind == "sam3" else "sam2.1-tiny-v1",
        "proposer_kind": kind,
        "proposal_metadata_source_reference": proposals,
        "metadata": {
            "proposals": proposer,
            "frame": model.profile_metadata("frame"),
            "regions": model.profile_metadata("regions", proposer),
        },
    }
    registry_from_bioclip_config(config)
    return config
