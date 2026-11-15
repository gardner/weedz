"""Resident model factories and explicit metadata captured by a real model preflight."""

from functools import cache
from pathlib import Path
from typing import Any, cast

from weedz.batches.activities import BatchRegistry
from weedz.batches.profiles import ModelProfile
from weedz.classification.batch import Profile, classifier_metadata
from weedz.classification.plantclef import PlantClassifier
from weedz.classification.regions import Proposer, regional_metadata
from weedz.segmentation.regions import ProposalConfig
from weedz.segmentation.sam2 import CHECKPOINT_SHA256, Sam2Proposer
from weedz.segmentation.sam3_image import Sam3Config, Sam3Image


class ClassifierView:
    def __init__(self, model: Any, metadata: dict) -> None:
        self.model, self.metadata = model, metadata

    def predict(self, images, top_k=5):
        return self.model.predict(images, top_k=top_k)


def prepare_config(
    root: Path,
    sam_checkpoint: Path,
    checkpoint: Path,
    labels: Path,
    device: str = "cuda:0",
    *,
    proposer_kind: Proposer = "sam2",
    sam3_config: Sam3Config | None = None,
) -> dict:
    model_cache = root / "temporal-model-cache"
    if proposer_kind == "sam3":
        if device != "cuda:0":
            raise ValueError(
                "SAM3 uses logical cuda:0; select its physical GPU with CUDA_VISIBLE_DEVICES"
            )
        sam = Sam3Image.load(sam_checkpoint, sam3_config or Sam3Config(), model_cache / "sam3")
    else:
        sam = Sam2Proposer(
            sam_checkpoint, CHECKPOINT_SHA256, model_cache / "sam2", ProposalConfig(), device
        )
    classifier = PlantClassifier.load(checkpoint, labels, device)
    return {
        "schema": 1,
        "artifact_root": str(root.resolve()),
        "device": device,
        "sam_checkpoint": str(sam_checkpoint.resolve()),
        "classifier_checkpoint": str(checkpoint.resolve()),
        "classifier_labels": str(labels.resolve()),
        "model_cache": str(model_cache.resolve()),
        "proposer_kind": proposer_kind,
        "segmentation_profile": "sam3-image-concept-v1"
        if proposer_kind == "sam3"
        else "sam2.1-tiny-v1",
        "classifier_profile": "plantclef-sam3-v3" if proposer_kind == "sam3" else "plantclef-v2",
        "metadata": {
            "proposals": sam.metadata,
            "frame": classifier_metadata(classifier, "frame"),
            "tiles": classifier_metadata(classifier, "tiles"),
            "regions": regional_metadata(classifier, sam.metadata, proposer_kind),
        },
    }


def _custom_registry(config: dict) -> BatchRegistry | None:
    kind = config.get("classifier_kind", "plantclef")
    if kind == "bioclip-margin-cuda-v1":
        from weedz.batches.bioclip_runtime import registry_from_bioclip_config

        return registry_from_bioclip_config(config)
    if kind == "weedscan-ort-cpu-v1":
        from weedz.batches.weedscan_runtime import registry_from_weedscan_config

        return registry_from_weedscan_config(config)
    if kind == "aotearoa-onnx-cpu-v1":
        if config.get("cache_only") is True:
            raise ValueError("Aotearoa frame inference is not a cache-only adoption registry")
        from weedz.batches.aotearoa_runtime import registry_from_aotearoa_config

        return registry_from_aotearoa_config(config)
    if kind != "plantclef":
        raise ValueError("Unknown configured classifier kind")
    return None


def registry_from_config(config: dict) -> BatchRegistry:
    if (custom := _custom_registry(config)) is not None:
        return custom
    if config.get("cache_only") is True:
        from weedz.batches.adoption import adoption_registry

        return adoption_registry(config)
    metadata = config["metadata"]
    device = config["device"]
    proposer_kind = config.get("proposer_kind", "sam2")
    if proposer_kind not in {"sam2", "sam3"}:
        raise ValueError("Unknown configured segmentation model kind")

    @cache
    def sam():
        if proposer_kind == "sam3":
            return Sam3Image.load(
                Path(config["sam_checkpoint"]),
                Sam3Config(**metadata["proposals"]["config"]),
                Path(config["model_cache"]) / "sam3",
            )
        return Sam2Proposer(
            Path(config["sam_checkpoint"]),
            CHECKPOINT_SHA256,
            Path(config["model_cache"]) / "sam2",
            ProposalConfig(**metadata["proposals"]["proposal_config"]),
            device,
        )

    @cache
    def classifier():
        return PlantClassifier.load(
            Path(config["classifier_checkpoint"]), Path(config["classifier_labels"]), device
        )

    def view(kind: str):
        model = classifier()
        actual = (
            regional_metadata(model, metadata["proposals"], cast(Proposer, proposer_kind))
            if kind == "regions"
            else classifier_metadata(model, cast(Profile, kind))
        )
        return ClassifierView(model, actual)

    return BatchRegistry(
        {
            config["segmentation_profile"]: ModelProfile(
                config["segmentation_profile"], "proposals", metadata["proposals"], sam
            )
        },
        {
            config["classifier_profile"]: {
                kind: ModelProfile(
                    config["classifier_profile"],
                    kind,
                    metadata[kind],
                    lambda kind=kind: view(kind),
                )
                for kind in ("frame", "tiles", "regions")
            }
        },
        {config["segmentation_profile"]: cast(Proposer, proposer_kind)},
    )
