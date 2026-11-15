"""Atomic per-photo evidence, bound to exact stage inputs and output bytes."""

import fcntl
import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any, Literal

Stage = Literal["proposals", "views"]
MAX_ARTIFACT_BYTES = 32_000_000


def digest(value: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, allow_nan=False).encode()).hexdigest()


def evidence_priority(result: dict) -> int:
    """Completed views dominate retained proposals, which dominate proposal failure."""
    if result.get("view_status") in {"ok", "empty"}:
        return 2
    return int(result.get("proposal_status") in {"ok", "empty"})


def sync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def durable_mkdir(path: Path) -> None:
    missing = []
    current = path
    while not current.exists():
        missing.append(current)
        current = current.parent
    for directory in reversed(missing):
        directory.mkdir(exist_ok=True)
        sync_directory(directory.parent)


class StageArtifacts:
    def __init__(self, root: Path, run_id: str) -> None:
        if Path(run_id).name != run_id or run_id in {"", ".", ".."}:
            raise ValueError("Invalid run artifact namespace")
        self.base = root
        self.root = root / "runs" / run_id / "pipeline-v1"

    def _path(self, stage: Stage, photo_id: str) -> Path:
        name = hashlib.sha256(photo_id.encode()).hexdigest()
        return self.root / f"{name}.{stage}.json"

    def entry(self, stage: Stage, photo_id: str) -> dict[str, Any] | None:
        path = self._path(stage, photo_id)
        if not path.exists():
            return None
        if path.stat().st_size > MAX_ARTIFACT_BYTES:
            raise ValueError("Stage artifact exceeds resource cap")
        record = json.loads(path.read_text())
        if not isinstance(record, dict) or record.get("schema") != 1:
            raise ValueError("Invalid stage artifact schema")
        payload = {key: record.get(key) for key in ("stage", "photo_id", "inputs", "result")}
        if record.get("sha256") != digest(payload):
            raise ValueError("Stage artifact checksum mismatch")
        if record["stage"] != stage or record["photo_id"] != photo_id:
            raise ValueError("Stage artifact provenance mismatch")
        if not isinstance(record["inputs"], dict) or not isinstance(record["result"], dict):
            raise ValueError("Invalid stage evidence")
        self._sync_hierarchy()
        return record

    def _sync_hierarchy(self) -> None:
        directory = self.root
        while directory != self.base:
            sync_directory(directory)
            directory = directory.parent
        sync_directory(self.base)

    def read(self, stage: Stage, photo_id: str, inputs: dict[str, Any]) -> dict[str, Any] | None:
        record = self.entry(stage, photo_id)
        if record is None:
            return None
        if record["inputs"] != inputs:
            raise ValueError("Stage artifact provenance changed; start a new run")
        return record["result"]

    def write(self, stage: Stage, photo_id: str, inputs: dict[str, Any], result: dict) -> dict:
        durable_mkdir(self.root)
        # A previous interrupted sync can leave existing but unacknowledged entries.
        # Re-establish the whole artifact hierarchy before even a cached success returns.
        self._sync_hierarchy()
        with self._path(stage, photo_id).with_suffix(".lock").open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            return self._write(stage, photo_id, inputs, result)

    def _write(self, stage: Stage, photo_id: str, inputs: dict[str, Any], result: dict) -> dict:
        previous = self.read(stage, photo_id, inputs)
        if previous and (
            previous.get("status") in {"ok", "empty"}
            or (stage == "views" and evidence_priority(previous) > evidence_priority(result))
        ):
            return previous
        payload = {"stage": stage, "photo_id": photo_id, "inputs": inputs, "result": result}
        encoded = json.dumps({"schema": 1, **payload, "sha256": digest(payload)}, allow_nan=False)
        if len(encoded.encode()) > MAX_ARTIFACT_BYTES:
            raise ValueError("Stage artifact exceeds resource cap")
        with tempfile.NamedTemporaryFile(mode="w", dir=self.root, delete=False) as stream:
            temporary = Path(stream.name)
            try:
                stream.write(encoded)
                stream.flush()
                os.fsync(stream.fileno())
                os.replace(temporary, self._path(stage, photo_id))
                sync_directory(self.root)
            finally:
                temporary.unlink(missing_ok=True)
        return result
