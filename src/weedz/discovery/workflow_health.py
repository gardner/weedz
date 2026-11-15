"""Owner-private scoped worker heartbeats; server reachability is checked separately."""

import json
import math
import os
import stat
import tempfile
import time
from pathlib import Path

from weedz.discovery.hosting import TemporalConnection

MAX_AGE_SECONDS = 20


def publish_worker_health(
    path: Path,
    connection: TemporalConnection,
    identity: str,
    *,
    now: float | None = None,
) -> None:
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    if path.parent.stat().st_mode & 0o077:
        raise ValueError("Worker health must live in an owner-private directory")
    payload = {
        "schema": 1,
        "address": connection.target,
        "namespace": connection.namespace,
        "task_queue": connection.task_queue,
        "identity": identity,
        "pid": os.getpid(),
        "updated_at": time.time() if now is None else now,
    }
    descriptor, temporary = tempfile.mkstemp(prefix=".worker-health-", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w") as stream:
            json.dump(payload, stream)
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def _read(path: Path) -> dict[str, object]:
    metadata = path.lstat()
    if not stat.S_ISREG(metadata.st_mode) or metadata.st_size > 4096 or metadata.st_mode & 0o077:
        raise ValueError("Invalid private worker heartbeat")
    record = json.loads(path.read_text())
    if not isinstance(record, dict):
        raise ValueError("Invalid worker heartbeat shape")
    return record


def worker_is_ready(
    path: Path, connection: TemporalConnection, *, now: float | None = None
) -> bool:
    try:
        record = _read(path)
        if any(
            record.get(key) != expected
            for key, expected in (
                ("schema", 1),
                ("address", connection.target),
                ("namespace", connection.namespace),
                ("task_queue", connection.task_queue),
            )
        ):
            return False
        updated = record.get("updated_at")
        if (
            not isinstance(updated, (int, float))
            or isinstance(updated, bool)
            or not math.isfinite(updated)
        ):
            return False
        age = (time.time() if now is None else now) - updated
        if not -2 <= age <= MAX_AGE_SECONDS:
            return False
        pid = record.get("pid")
        if type(pid) is not int or pid <= 0 or not record.get("identity"):
            return False
        os.kill(pid, 0)
        return True
    except (OSError, ValueError, TypeError, OverflowError):
        return False


def clear_worker_health(path: Path, identity: str) -> None:
    try:
        if _read(path).get("identity") == identity:
            path.unlink()
    except (OSError, ValueError, TypeError):
        pass
