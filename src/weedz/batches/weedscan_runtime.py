"""CPU WeedScan frame/region workers consume verified SAM evidence without rerunning SAM."""

import json
from functools import cache
from pathlib import Path

from weedz.annotation.weedscan import identity as weedscan_identity
from weedz.batches.activities import BatchRegistry
from weedz.batches.profiles import Kind, ModelProfile, sam_identity
from weedz.batches.storage import read_artifact
from weedz.classification.batch import classifier_metadata
from weedz.classification.regions import Proposer, regional_metadata
from weedz.classification.weedscan import WeedScanClassifier
from weedz.segmentation.artifacts import digest

KIND = "weedscan-ort-cpu-v1"
PROFILE = "weedscan488-v1"


def _no_sam():
    raise RuntimeError(
        "WeedScan classifier workers never run SAM; supply verified cached proposals"
    )


class WeedScanRegistry(BatchRegistry):
    def pins(self, request: dict) -> dict[str, str]:
        if not set(request["variants"]).issubset({"frame", "regions"}):
            raise ValueError("WeedScan supports frame and regions only")
        if not request["cached"].get("proposals"):
            raise ValueError("WeedScan requires a verified cached proposal artifact")
        return super().pins(request)


def _proposer_kind(proposer: dict) -> Proposer:
    sam_identity(proposer)
    return "sam3" if proposer.get("profile") == "sam3-image-concept-v1" else "sam2"


def registry_from_weedscan_config(config: dict) -> BatchRegistry:
    if config.get("classifier_kind") != KIND or config.get("device") != "cpu":
        raise ValueError("Unknown WeedScan classifier kind or CPU device")
    if config.get("cache_only") is True:
        raise ValueError("WeedScan inference is not a cache-only adoption registry")
    metadata = config["metadata"]
    proposer = metadata["proposals"]
    kind = _proposer_kind(proposer)
    if config.get("proposer_kind") != kind:
        raise ValueError("WeedScan proposer kind disagrees with the cached SAM metadata")
    for variant in ("frame", "regions"):
        weedscan_identity(metadata[variant], variant)
    if digest(sam_identity(metadata["regions"]["proposer"])) != digest(sam_identity(proposer)):
        raise ValueError("WeedScan regional and registered proposer metadata disagree")

    @cache
    def classifier():
        return WeedScanClassifier.load(
            Path(config["classifier_checkpoint"]), Path(config["classifier_labels"])
        )

    def view(variant: Kind):
        from weedz.batches.runtime import ClassifierView

        model = classifier()
        actual = (
            regional_metadata(model, proposer, kind)
            if variant == "regions"
            else classifier_metadata(model, "frame")
        )
        return ClassifierView(model, actual)

    sam_name, group = config["segmentation_profile"], config["classifier_profile"]
    return WeedScanRegistry(
        {sam_name: ModelProfile(sam_name, "proposals", proposer, _no_sam)},
        {
            group: {
                variant: ModelProfile(
                    group,
                    variant,
                    metadata[variant],
                    lambda variant=variant: view(variant),
                    identity=weedscan_identity,
                )
                for variant in ("frame", "regions")
            }
        },
        {sam_name: kind},
    )


def prepare_weedscan_config(root: Path, checkpoint: Path, labels: Path, proposals: dict) -> dict:
    encoded = read_artifact(root.resolve(), proposals, 128_000_000)
    rows = [json.loads(line) for line in encoded.splitlines()]
    if not 1 <= len(rows) <= 1000:
        raise ValueError("Use a nonempty bounded completed SAM proposal batch")
    proposer = rows[0]["segmentation"]["provenance"]
    if any(row["segmentation"]["provenance"] != proposer for row in rows):
        raise ValueError("Mixed proposal provenance")
    kind = _proposer_kind(proposer)
    model = WeedScanClassifier.load(checkpoint, labels)
    config = {
        "schema": 1,
        "artifact_root": str(root.resolve()),
        "classifier_kind": KIND,
        "device": "cpu",
        "classifier_checkpoint": str(checkpoint.resolve()),
        "classifier_labels": str(labels.resolve()),
        "classifier_profile": PROFILE,
        "segmentation_profile": "sam3-image-concept-v1" if kind == "sam3" else "sam2.1-tiny-v1",
        "proposer_kind": kind,
        "metadata": {
            "proposals": proposer,
            "frame": classifier_metadata(model, "frame"),
            "regions": regional_metadata(model, proposer, kind),
        },
        "proposal_metadata_source_reference": proposals,
    }
    registry_from_weedscan_config(config)
    return config
