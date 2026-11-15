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


class StageArtifacts:
    def __init__(self, root: Path, run_id: str) -> None:
        if Path(run_id).name != run_id or run_id in {"", ".", ".."}:
            raise ValueError("Invalid run artifact namespace")
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
        return record

    def read(self, stage: Stage, photo_id: str, inputs: dict[str, Any]) -> dict[str, Any] | None:
        record = self.entry(stage, photo_id)
        if record is None:
            return None
        if record["inputs"] != inputs:
            raise ValueError("Stage artifact provenance changed; start a new run")
        return record["result"]

    def write(self, stage: Stage, photo_id: str, inputs: dict[str, Any], result: dict) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        with self._path(stage, photo_id).with_suffix(".lock").open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            self._write(stage, photo_id, inputs, result)

    def _write(self, stage: Stage, photo_id: str, inputs: dict[str, Any], result: dict) -> None:
        previous = self.read(stage, photo_id, inputs)
        if previous and previous.get("status") in {"ok", "empty"}:
            if previous != result:
                raise ValueError("A completed stage artifact cannot be replaced by a late retry")
            return
        payload = {"stage": stage, "photo_id": photo_id, "inputs": inputs, "result": result}
        encoded = json.dumps({"schema": 1, **payload, "sha256": digest(payload)}, allow_nan=False)
        if len(encoded.encode()) > MAX_ARTIFACT_BYTES:
            raise ValueError("Stage artifact exceeds resource cap")
        self.root.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(mode="w", dir=self.root, delete=False) as stream:
            temporary = Path(stream.name)
            try:
                stream.write(encoded)
                stream.flush()
                os.fsync(stream.fileno())
                os.replace(temporary, self._path(stage, photo_id))
            finally:
                temporary.unlink(missing_ok=True)
