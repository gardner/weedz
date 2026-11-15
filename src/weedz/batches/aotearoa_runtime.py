"""CPU NZ frame inference with explicit reuse of already-completed SAM evidence."""

import json
from functools import cache
from pathlib import Path

from weedz.batches.activities import BatchRegistry
from weedz.batches.profiles import Kind, ModelProfile
from weedz.batches.storage import read_artifact
from weedz.classification.aotearoa import (
    CLASS_COUNT,
    LABELS_SHA256,
    RELEASE,
    WEIGHTS_SHA256,
    AotearoaClassifier,
)
from weedz.classification.batch import classifier_metadata

KIND = "aotearoa-onnx-cpu-v1"
PROFILE = "aotearoa-nz-frame-v1"


def aotearoa_identity(metadata: dict, kind: Kind) -> dict:
    if kind != "frame":
        raise ValueError("Aotearoa supports only the released CPU frame profile")
    expected = {
        "pipeline_name": "Aotearoa NZ",
        "weights_sha256": WEIGHTS_SHA256,
        "labels_sha256": LABELS_SHA256,
        "class_count": CLASS_COUNT,
        "device": "cpu",
        "precision": "float32",
        "release": RELEASE,
        "supported_profiles": ["frame"],
    }
    if any(metadata.get(key) != value for key, value in expected.items()):
        raise ValueError("Aotearoa model identity or CPU frame policy disagrees")
    strings = ("model", "revision", "onnxruntime", "numpy", "pillow", "input_policy", "score_kind")
    if any(not isinstance(metadata.get(key), str) or not metadata[key].strip() for key in strings):
        raise ValueError("Incomplete Aotearoa runtime identity")
    if not isinstance(metadata.get("preprocessing"), dict) or not metadata["preprocessing"]:
        raise ValueError("Missing Aotearoa preprocessing identity")
    # All recorded fields are normative: do not borrow PlantCLEF torch/timm assumptions.
    return metadata


def _no_sam_inference():
    raise RuntimeError("Aotearoa frame workers never run SAM; supply verified cached proposals")


class AotearoaRegistry(BatchRegistry):
    def pins(self, request: dict) -> dict[str, str]:
        if request["variants"] != ["frame"]:
            raise ValueError("Aotearoa supports only frame classification")
        if not request["cached"].get("proposals"):
            raise ValueError("Aotearoa workflows require a cached proposal artifact")
        return super().pins(request)


def registry_from_aotearoa_config(config: dict) -> BatchRegistry:
    if config.get("classifier_kind") != KIND or config.get("device", "cpu") != "cpu":
        raise ValueError("Unknown Aotearoa classifier kind or device")
    metadata = config["metadata"]
    aotearoa_identity(metadata["frame"], "frame")

    @cache
    def classifier():
        from weedz.batches.runtime import ClassifierView

        model = AotearoaClassifier.load(
            Path(config["classifier_checkpoint"]), Path(config["classifier_labels"])
        )
        return ClassifierView(model, classifier_metadata(model, "frame"))

    sam_name, frame_name = config["segmentation_profile"], config["classifier_profile"]
    return AotearoaRegistry(
        {sam_name: ModelProfile(sam_name, "proposals", metadata["proposals"], _no_sam_inference)},
        {
            frame_name: {
                "frame": ModelProfile(
                    f"{frame_name}-frame",
                    "frame",
                    metadata["frame"],
                    classifier,
                    identity=aotearoa_identity,
                )
            }
        },
        {sam_name: "sam2"},
    )


def prepare_aotearoa_config(root: Path, checkpoint: Path, labels: Path, proposals: dict) -> dict:
    encoded = read_artifact(root.resolve(), proposals, 128_000_000)
    rows = [json.loads(line) for line in encoded.splitlines()]
    if not rows or len(rows) > 1000:
        raise ValueError("Use a nonempty bounded completed SAM2 proposal batch")
    proposer = rows[0]["segmentation"]["provenance"]
    if any(row["segmentation"]["provenance"] != proposer for row in rows):
        raise ValueError("Mixed proposal provenance")
    if proposer.get("profile") not in {None, "sam2.1-tiny-v1"}:
        raise ValueError("This frame variant adopts existing SAM2 evidence only")
    model = AotearoaClassifier.load(checkpoint, labels)
    result = {
        "schema": 1,
        "artifact_root": str(root.resolve()),
        "classifier_kind": KIND,
        "device": "cpu",
        "classifier_checkpoint": str(checkpoint.resolve()),
        "classifier_labels": str(labels.resolve()),
        "classifier_profile": PROFILE,
        "segmentation_profile": "sam2.1-tiny-v1",
        "proposer_kind": "sam2",
        "metadata": {"frame": classifier_metadata(model, "frame"), "proposals": proposer},
        "proposal_preflight_reference": proposals,
    }
    registry_from_aotearoa_config(result)
    return result
