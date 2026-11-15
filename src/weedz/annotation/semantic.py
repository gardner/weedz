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
CONFIG_FIELDS = {
    "max_side",
    "points_per_side",
    "points_per_batch",
    "max_proposals",
    "min_area",
    "context_fraction",
}


def _fields(metadata: dict[str, Any], fields: tuple[str, ...]) -> dict[str, Any]:
    if any(key not in metadata or metadata[key] is None for key in fields):
        raise ValueError("Incomplete semantic pipeline metadata")
    return {key: metadata[key] for key in fields}


def shared_regional_version(metadata: dict[str, Any]) -> dict[str, Any]:
    classifier = metadata.get("classifier", metadata)
    if not isinstance(classifier, dict):
        raise ValueError("Invalid semantic pipeline metadata")
    proposer = metadata.get(
        "proposer", classifier.get("proposer", metadata.get("proposal_experiment", {}))
    )
    if not isinstance(proposer, dict):
        raise ValueError("Invalid semantic pipeline metadata")
    config = proposer.get("proposal_config", proposer.get("config"))
    if not isinstance(config, dict) or not CONFIG_FIELDS.issubset(config):
        raise ValueError("Incomplete semantic proposal configuration")
    semantic = {
        "classifier": _fields(classifier, CLASSIFIER_FIELDS),
        "proposer": {**_fields(proposer, PROPOSER_FIELDS), "proposal_config": config},
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
    encoded = json.dumps(semantic, sort_keys=True, allow_nan=False).encode()
    stamp = hashlib.sha256(encoded).hexdigest()
    return {
        "model_version": f"SAM2.1 + PlantCLEF masked v1 · {stamp[:8]}",
        "sha256": stamp,
        "semantic": semantic,
    }
