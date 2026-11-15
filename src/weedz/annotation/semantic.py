"""Stable inference identities, independent of corpus notes and metadata nesting."""

import hashlib
import json
from typing import Any

from weedz.discovery.records import SPECIES

CLASSIFIER_FIELDS = (
    "repository",
    "revision",
    "weights_sha256",
    "labels_sha256",
    "class_count",
    "preprocessing",
    "precision",
    "timm",
    "torch",
    "score_kind",
)
PROPOSER_FIELDS = (
    "model",
    "code_revision",
    "checkpoint_sha256",
    "mask_filter",
    "transforms_revision",
    "class_agnostic",
    "crop_layers",
    "postprocessing",
    "torch",
    "torchvision",
    "pillow",
    "numpy",
)
SAM3_PROPOSER_FIELDS = (
    "model",
    "profile",
    "code_revision",
    "checkpoint_revision",
    "checkpoint_sha256",
    "processor_resolution",
    "processor_output_threshold",
    "mask_probability_threshold",
    "score_kind",
    "calibrated",
    "precision",
    "torch",
    "numpy",
    "pillow",
    "config",
)

CONFIG_FIELDS = {
    "max_side",
    "points_per_side",
    "points_per_batch",
    "max_proposals",
    "min_area",
    "context_fraction",
}


def classifier_runtime(metadata: dict[str, Any]) -> dict[str, Any]:
    """Absent historical pins stay unknown; new declarations must be a complete pair."""
    if metadata.get("pipeline_name") == "WeedScan488":
        from weedz.annotation.weedscan import runtime

        return runtime(metadata)
    classifier = metadata.get("classifier", metadata)
    if not isinstance(classifier, dict):
        raise ValueError("Invalid classifier runtime metadata")
    fields = ("pillow", "torchvision")
    present = [key in classifier for key in fields]
    if not any(present):
        return {"status": "historical_unrecorded", "pillow": None, "torchvision": None}
    if not all(present) or any(
        not isinstance(classifier[key], str) or not classifier[key].strip() for key in fields
    ):
        raise ValueError("Classifier runtime requires nonblank Pillow and torchvision versions")
    return {"status": "recorded", **{key: classifier[key] for key in fields}}


def classifier_numerics(classifier: dict[str, Any]) -> dict[str, Any]:
    """Bind recorded numeric policies without inventing absent historical declarations."""
    result = {}
    if "numpy" in classifier:
        value = classifier["numpy"]
        if not isinstance(value, str) or not value.strip():
            raise ValueError("Classifier NumPy version must be nonblank")
        result["numpy"] = value
    if "math_policy" in classifier:
        policy = classifier["math_policy"]
        if (
            not isinstance(policy, dict)
            or set(policy) != {"cuda_matmul_tf32", "cudnn_tf32", "autocast"}
            or any(type(value) is not bool for value in policy.values())
        ):
            raise ValueError("Invalid classifier math policy")
        result["math_policy"] = policy
    return result


def _fields(metadata: dict[str, Any], fields: tuple[str, ...]) -> dict[str, Any]:
    if any(key not in metadata or metadata[key] is None for key in fields):
        raise ValueError("Incomplete semantic pipeline metadata")
    return {key: metadata[key] for key in fields}


def proposer_semantic(proposer: dict[str, Any]) -> tuple[dict[str, Any], str]:
    profile = proposer.get("profile")
    if profile == "sam3-image-concept-v1":
        config = proposer.get("config")
        required = {
            "prompts",
            "max_side",
            "max_regions",
            "min_area",
            "concept_threshold",
            "context_fraction",
        }
        if not isinstance(config, dict) or not required.issubset(config):
            raise ValueError("Incomplete SAM3 semantic proposal configuration")
        return _fields(proposer, SAM3_PROPOSER_FIELDS), "SAM3"
    if profile not in {None, "sam2.1-tiny-v1"}:
        raise ValueError("Unknown semantic proposer profile")
    config = proposer.get("proposal_config", proposer.get("config"))
    if not isinstance(config, dict) or not CONFIG_FIELDS.issubset(config):
        raise ValueError("Incomplete semantic proposal configuration")
    return {**_fields(proposer, PROPOSER_FIELDS), "proposal_config": config}, "SAM2.1"


def shared_regional_version(metadata: dict[str, Any]) -> dict[str, Any]:
    if metadata.get("pipeline_name") == "WeedScan488":
        from weedz.annotation.weedscan import regional_version

        return regional_version(metadata)
    classifier = metadata.get("classifier", metadata)
    if not isinstance(classifier, dict):
        raise ValueError("Invalid semantic pipeline metadata")
    proposer = metadata.get(
        "proposer", classifier.get("proposer", metadata.get("proposal_experiment", {}))
    )
    if not isinstance(proposer, dict):
        raise ValueError("Invalid semantic pipeline metadata")
    normalized_proposer, name = proposer_semantic(proposer)
    runtime = classifier_runtime(metadata)
    optional = (
        {key: runtime[key] for key in ("pillow", "torchvision")}
        if runtime["status"] == "recorded"
        else {}
    )
    optional.update(classifier_numerics(classifier))
    semantic = {
        "classifier": {**_fields(classifier, CLASSIFIER_FIELDS), **optional},
        "proposer": normalized_proposer,
        "assignment": {
            "primary_view": "masked",
            "selection": "first returned top-k taxon",
            "watchlist": sorted(SPECIES),
            "match": "exact binomial or binomial followed by space",
            "other_taxa": "Other plant",
            "missing_or_nonfinite": "Unknown",
            "taxon_text": "exact returned taxon; editable; never verified automatically",
            "nonplant_rejection": False,
        },
        "mask_transform": "alpha>0; nearest-neighbour to upright source; v1",
    }
    semantic.update(
        {
            key: metadata[key]
            for key in ("crop_geometry_revision", "masked_view_policy")
            if key in metadata
        }
    )
    encoded = json.dumps(semantic, sort_keys=True, allow_nan=False).encode()
    stamp = hashlib.sha256(encoded).hexdigest()
    return {
        "model_version": f"{name} + PlantCLEF masked v1 · {stamp[:8]}",
        "sha256": stamp,
        "semantic": semantic,
    }
