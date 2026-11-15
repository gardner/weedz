"""Append-only Label Studio REST writes under the existing sole-writer lock."""

import hashlib
import os
import tempfile
from collections.abc import Callable
from contextlib import suppress
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlsplit

import httpx

from weedz.batches.package import Package, validate_package
from weedz.batches.publication_state import Intents, writer_lock
from weedz.batches.storage import read_artifact, read_owned_file
from weedz.segmentation.artifacts import durable_mkdir, sync_directory

Index = dict[str, dict[str, Any]]


def _require(response: httpx.Response) -> dict:
    if not response.is_success:
        raise RuntimeError(
            f"Label Studio {response.request.method} failed ({response.status_code})"
        )
    return response.json()


def _predictions(client: httpx.Client, task: int) -> dict[str, list]:
    body = _require(client.get(f"/api/tasks/{task}/"))
    result = {}
    for prediction in body["predictions"]:
        version = prediction["model_version"]
        if version in result:
            raise ValueError("Existing task has duplicate prediction model versions")
        result[version] = prediction["result"]
    return result


def _image_address(address: str) -> tuple:
    url = urlsplit(address)
    return url.scheme, url.netloc, url.path, parse_qs(url.query), url.fragment


def _missing(
    client: httpx.Client,
    tasks: tuple[dict, ...],
    index: Index,
    intents: Intents,
    heartbeat: Callable[[], None],
) -> list[dict]:
    missing = []
    for task in tasks:
        heartbeat()
        key = task["meta"]["external_id"]
        if key not in index:
            continue
        current = index[key]
        if _image_address(current["data"]["image"]) != _image_address(task["data"]["image"]):
            raise ValueError("Existing task image differs from the canonical publication")
        existing = _predictions(client, current["id"])
        intents.complete(f"task:{key}")
        for prediction in task.get("predictions", []):
            version = prediction["model_version"]
            if version in existing:
                if existing[version] != prediction["result"]:
                    raise ValueError("Same pipeline version has conflicting results")
                intents.complete(f"prediction:{current['id']}:{version}")
            else:
                missing.append({"task": current["id"], **prediction})
    return missing


def _copy_images(package: Package, destination: Path, heartbeat: Callable[[], None]) -> None:
    for name, reference in package.images.items():
        heartbeat()
        encoded = read_artifact(package.root, reference, 160_000_000)
        target = destination / name
        if not target.resolve().is_relative_to(destination.resolve()):
            raise ValueError("Publication image escapes its configured storage")
        durable_mkdir(target.parent)
        if target.exists():
            digest = hashlib.sha256(read_owned_file(target, destination, 160_000_000)).hexdigest()
            if digest != reference["sha256"]:
                raise ValueError("Published image checksum mismatch")
            continue
        with tempfile.NamedTemporaryFile(dir=target.parent, delete=False) as stream:
            temporary = Path(stream.name)
            try:
                stream.write(encoded)
                stream.flush()
                os.fsync(stream.fileno())
                os.link(temporary, target)
            finally:
                temporary.unlink(missing_ok=True)
        sync_directory(target.parent)


def _import_tasks(
    client: httpx.Client,
    project: int,
    tasks: list[dict],
    index: Callable[[], Index],
    intents: Intents,
) -> Index:
    for task in tasks:
        if intents.pending(f"task:{task['meta']['external_id']}"):
            raise RuntimeError("Task import outcome is uncertain; awaiting server reconciliation")
    for task in tasks:
        intents.begin(f"task:{task['meta']['external_id']}", task)
    # A timeout is not a refusal. Re-index before deciding what remains unresolved.
    with suppress(httpx.TimeoutException, httpx.NetworkError):
        _require(
            client.post(
                f"/api/projects/{project}/import", params={"return_task_ids": "true"}, json=tasks
            )
        )
    current = index()
    if any(task["meta"]["external_id"] not in current for task in tasks):
        raise RuntimeError("Task import outcome is uncertain; no automatic duplicate POST is safe")
    return current


def _append_predictions(
    client: httpx.Client,
    project: int,
    missing: list[dict],
    intents: Intents,
    heartbeat: Callable[[], None],
) -> None:
    for start in range(0, len(missing), 32):
        heartbeat()
        chunk = missing[start : start + 32]
        for prediction in chunk:
            key = f"prediction:{prediction['task']}:{prediction['model_version']}"
            if intents.pending(key):
                raise RuntimeError(
                    "Prediction outcome is uncertain; awaiting server reconciliation"
                )
        for prediction in chunk:
            intents.begin(
                f"prediction:{prediction['task']}:{prediction['model_version']}", prediction
            )
        with suppress(httpx.TimeoutException, httpx.NetworkError):
            _require(client.post(f"/api/projects/{project}/import/predictions", json=chunk))
        for prediction in chunk:
            heartbeat()
            current = _predictions(client, prediction["task"])
            if current.get(prediction["model_version"]) != prediction["result"]:
                raise RuntimeError("Prediction publication outcome is uncertain or conflicting")
            intents.complete(f"prediction:{prediction['task']}:{prediction['model_version']}")


def publish(
    package: Package,
    project: int,
    client: httpx.Client,
    index: Callable[[], Index],
    images: Path,
    state: Path,
    lock: Path,
    heartbeat: Callable[[], None] = lambda: None,
) -> dict:
    if type(project) is not int or project <= 0:
        raise ValueError("Choose a positive Label Studio project")
    # Re-read pinned bytes instead of trusting mutable nested dictionaries from a caller.
    package = validate_package(package.root, package.sha256, heartbeat)
    with writer_lock(lock, heartbeat):
        intents = Intents(state, project)
        current = index()
        # Discover conflicts before importing new tasks or appending any model output.
        _missing(client, package.tasks, current, intents, heartbeat)
        _copy_images(package, images, heartbeat)
        new = [task for task in package.tasks if task["meta"]["external_id"] not in current]
        if new:
            current = _import_tasks(client, project, new, index, intents)
        missing = _missing(client, package.tasks, current, intents, heartbeat)
        _append_predictions(client, project, missing, intents, heartbeat)
        heartbeat()
        return {
            "schema": 1,
            "project_id": project,
            "package_sha256": package.sha256,
            "tasks": len(package.tasks),
            "new_tasks": len(new),
            "new_predictions": len(missing),
            "human_annotation_writes": 0,
        }
