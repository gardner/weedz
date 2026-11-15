"""Validate all package bytes and canonical identities before any external write."""

import hashlib
import json
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlsplit

from weedz.batches.storage import read_artifact
from weedz.contract import Sample


@dataclass(frozen=True)
class Package:
    root: Path
    sha256: str
    tasks: tuple[dict[str, Any], ...]
    images: dict[str, dict[str, str]]


def _predictions(task: dict) -> None:
    rows = task.get("predictions", [])
    if not isinstance(rows, list) or len(rows) > 16:
        raise ValueError("Invalid machine prediction list")
    versions = []
    for prediction in rows:
        if not isinstance(prediction, dict) or set(prediction) != {"model_version", "result"}:
            raise ValueError("Only machine model_version/result predictions may be published")
        version, result = prediction["model_version"], prediction["result"]
        if (
            not isinstance(version, str)
            or not 1 <= len(version) <= 256
            or not isinstance(result, list)
        ):
            raise ValueError("Invalid machine prediction identity or result")
        versions.append(version)
    if len(set(versions)) != len(versions):
        raise ValueError("Duplicate model versions in publication package")


def _task(task: dict, sample: Sample, key: str, prefix: str, files: dict) -> tuple[str, dict]:
    if not isinstance(task, dict) or set(task) - {"data", "meta", "predictions"}:
        raise ValueError("Only machine predictions may be imported; human annotations are excluded")
    expected = hashlib.sha256(f"{sample.id}:{sample.media.sha256}".encode()).hexdigest()
    if key != expected or task["meta"].get("image_sha256") != sample.media.sha256:
        raise ValueError("Publication task and canonical sample identity disagree")
    relative = f"{prefix}/{sample.media.sha256}.png"
    address = urlsplit(task["data"]["image"])
    if (
        address.scheme
        or address.netloc
        or address.fragment
        or address.path != "/data/local-files/"
        or parse_qs(address.query) != {"d": [relative]}
    ):
        raise ValueError("Publication image must reference its exact canonical storage path")
    image = f"images/{relative}"
    if sample.media.uri != image or files.get(image) != sample.media.sha256:
        raise ValueError("Publication image checksum differs from its canonical sample")
    _predictions(task)
    return relative, {"path": image, "sha256": sample.media.sha256}


def _prefix(prefix: Any) -> str:
    if (
        not isinstance(prefix, str)
        or ":" in prefix
        or "\\" in prefix
        or any(part in {"", ".", ".."} for part in prefix.split("/"))
    ):
        raise ValueError("Invalid publication image prefix")
    return prefix


def _read_package(
    root: Path, manifest_sha256: str, heartbeat: Callable[[], None]
) -> tuple[dict, dict]:
    manifest = json.loads(
        read_artifact(root, {"path": "manifest.json", "sha256": manifest_sha256}, 1024 * 1024)
    )
    files = manifest.get("files")
    if not isinstance(files, dict) or not 1 <= len(files) <= 5000:
        raise ValueError("Invalid bounded publication package file list")
    retained = {}
    for name, sha in files.items():
        heartbeat()
        raw = read_artifact(root, {"path": name, "sha256": sha}, 160_000_000)
        if name in {"tasks.json", "private/provenance.json"}:
            retained[name] = json.loads(raw)
    return manifest, retained


def validate_package(
    root: Path, manifest_sha256: str, heartbeat: Callable[[], None] = lambda: None
) -> Package:
    root = root.resolve()
    manifest, retained = _read_package(root, manifest_sha256, heartbeat)
    files = manifest["files"]
    tasks, provenance = retained["tasks.json"], retained["private/provenance.json"]
    if not isinstance(tasks, list) or not 1 <= len(tasks) <= 1000:
        raise ValueError("Publish a bounded nonempty package")
    if type(manifest.get("task_count")) is not int or manifest["task_count"] != len(tasks):
        raise ValueError("Publication package task count disagrees")
    samples = {
        row["external_id"]: Sample.model_validate(row["sample"]) for row in provenance["samples"]
    }
    if len(samples) != len(provenance["samples"]) or len(samples) != len(tasks):
        raise ValueError("Publication canonical identities are incomplete or duplicated")
    prefix = _prefix(manifest["image_prefix"])
    images, keys = {}, set()
    for task in tasks:
        heartbeat()
        key = task["meta"]["external_id"]
        if key in keys or key not in samples:
            raise ValueError("Publication task identities are duplicated or unknown")
        keys.add(key)
        name, reference = _task(task, samples[key], key, prefix, files)
        images[name] = reference
    return Package(root, manifest_sha256, tuple(tasks), images)
