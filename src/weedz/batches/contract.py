"""Small deterministic workflow messages; model bytes and predictions stay on disk."""

import re
from typing import Any

DIGEST = re.compile(r"[0-9a-f]{64}")
PROFILE = re.compile(r"[a-z0-9][a-z0-9.-]{0,79}")
VARIANTS = ("frame", "tiles", "regions")


def artifact(value: Any) -> dict[str, str]:
    if not isinstance(value, dict) or set(value) != {"path", "sha256"}:
        raise ValueError("Activities exchange only immutable artifact references")
    path, digest = value["path"], value["sha256"]
    if (
        not isinstance(path, str)
        or not 1 <= len(path) <= 512
        or "\\" in path
        or ":" in path
        or any(part in {"", ".", ".."} for part in path.split("/"))
        or any(ord(character) < 32 for character in path)
        or not isinstance(digest, str)
        or DIGEST.fullmatch(digest) is None
    ):
        raise ValueError("Artifact requires a bounded relative path and SHA-256")
    return {"path": path, "sha256": digest}


def batch_request(value: Any) -> dict[str, Any]:
    fields = {
        "manifest",
        "ready",
        "segmentation_profile",
        "classifier_profile",
        "variants",
        "project_id",
    }
    if (
        not isinstance(value, dict)
        or not fields.issubset(value)
        or set(value) - fields - {"cached"}
    ):
        raise ValueError("Unknown or incomplete batch request")
    profiles = (value["segmentation_profile"], value["classifier_profile"])
    if any(not isinstance(p, str) or PROFILE.fullmatch(p) is None for p in profiles):
        raise ValueError("Choose registered versioned inference profiles")
    variants = value["variants"]
    if (
        not isinstance(variants, list)
        or not variants
        or any(v not in VARIANTS for v in variants)
        or len(set(variants)) != len(variants)
    ):
        raise ValueError("Choose distinct frame, tiles or regions variants")
    project = value["project_id"]
    if type(project) is not int or not 1 <= project <= 2**31 - 1:
        raise ValueError("Choose a positive Label Studio project ID")
    return {
        **value,
        "manifest": artifact(value["manifest"]),
        "ready": artifact(value["ready"]),
        "cached": cached_artifacts(value.get("cached", {}), variants),
    }


def cached_artifacts(value: Any, variants: list[str]) -> dict[str, dict[str, str]]:
    if not isinstance(value, dict) or set(value) - {"proposals", *variants}:
        raise ValueError("Cache references must name requested inference stages")
    return {name: artifact(reference) for name, reference in value.items()}
