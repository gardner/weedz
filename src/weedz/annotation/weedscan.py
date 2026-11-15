"""WeedScan identities and editable suggestions retain their actual ONNX provenance."""

import hashlib
import json
from typing import Any

from weedz.annotation.label_studio import evidence_result

POLICY = "top1 closed-set WeedScan taxon; uncalibrated; no unknown or nonplant rejection"
VIEWS = ["tight", "masked", "context"]


def runtime(metadata: dict[str, Any]) -> dict[str, Any]:
    keys = ("onnxruntime", "numpy", "pillow")
    if any(not isinstance(metadata.get(key), str) or not metadata[key].strip() for key in keys):
        raise ValueError("Incomplete WeedScan CPU runtime declaration")
    return {"status": "recorded", "framework": "onnxruntime", **{k: metadata[k] for k in keys}}


def identity(metadata: dict[str, Any], kind: str) -> dict[str, Any]:
    from weedz.classification.weedscan import CLASS_COUNT, LABELS_SHA256, RELEASE, WEIGHTS_SHA256

    expected = {
        "pipeline_name": "WeedScan488",
        "release": RELEASE,
        "weights_sha256": WEIGHTS_SHA256,
        "labels_sha256": LABELS_SHA256,
        "class_count": CLASS_COUNT,
        "device": "cpu",
        "precision": "float32",
        "score_kind": "closed_set_softmax_uncalibrated",
    }
    if any(metadata.get(key) != value for key, value in expected.items()):
        raise ValueError("WeedScan model identity or CPU policy disagrees")
    runtime(metadata)
    if not isinstance(metadata.get("preprocessing"), dict) or not metadata["preprocessing"]:
        raise ValueError("Missing WeedScan preprocessing identity")
    if not isinstance(metadata.get("input_policy"), str) or not metadata["input_policy"].strip():
        raise ValueError("Missing WeedScan input policy")
    if kind == "regions":
        from weedz.annotation.semantic import proposer_semantic

        proposer_semantic(metadata.get("proposer", {}))
        if metadata.get("views") != VIEWS or metadata.get("primary_view") != "masked":
            raise ValueError("WeedScan regional views or primary view disagree")
        if metadata.get("crop_geometry_revision") != 2 or not metadata.get("masked_view_policy"):
            raise ValueError("Missing WeedScan whole-region crop policy")
    elif kind != "frame":
        raise ValueError("WeedScan supports frame and regions only")
    # Preserve every declared model/runtime/transform field; do not invent timm/torch pins.
    return metadata


def regional_version(metadata: dict[str, Any]) -> dict[str, Any]:
    from weedz.annotation.semantic import proposer_semantic

    _, name = proposer_semantic(metadata.get("proposer", {}))
    classifier = identity(metadata, "regions")
    semantic = {"classifier": classifier, "assignment": POLICY, "primary_view": "masked"}
    stamp = hashlib.sha256(
        json.dumps(semantic, sort_keys=True, allow_nan=False).encode()
    ).hexdigest()
    return {
        "model_version": f"{name} + WeedScan488 masked v1 · {stamp[:8]}",
        "sha256": stamp,
        "semantic": semantic,
    }


def frame_prediction(topk: list[dict[str, Any]], metadata: dict[str, Any]) -> dict[str, Any]:
    from weedz.annotation.auto_labels import display_version, taxon_result, top_taxon

    identity(metadata, "frame")
    return {
        "model_version": display_version("WeedScan488 frame verification v1", metadata, POLICY),
        "result": [
            taxon_result(top_taxon(topk)),
            evidence_result(
                {
                    "interpretation": POLICY,
                    "scope": "whole frame under released centre crop; not plant boundaries",
                    "classifier_runtime": runtime(metadata),
                    "model": metadata,
                    "topk": topk,
                    "limitations": metadata.get("limitations", []),
                }
            ),
        ],
    }
