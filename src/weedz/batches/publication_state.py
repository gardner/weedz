"""One writer lock and durable ambiguous-request intents, never blind POST retries."""

import fcntl
import hashlib
import json
import os
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path

from weedz.batches.receipts import write_receipt
from weedz.segmentation.artifacts import durable_mkdir, sync_directory


@contextmanager
def writer_lock(path: Path, heartbeat: Callable[[], None], timeout: float = 60) -> Iterator[None]:
    durable_mkdir(path.parent)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    with os.fdopen(descriptor, "w") as stream:
        deadline = time.monotonic() + timeout
        while True:
            try:
                fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    raise TimeoutError("Annotation publisher is busy") from None
                heartbeat()
                time.sleep(0.1)
        yield


class Intents:
    def __init__(self, root: Path, project: int):
        durable_mkdir(root)
        self.root, self.project = root, project

    def path(self, key: str) -> Path:
        name = hashlib.sha256(key.encode()).hexdigest()
        return self.root / f"intents/project-{self.project}/{name}.json"

    def pending(self, key: str) -> bool:
        return self.path(key).exists()

    def begin(self, key: str, body: dict) -> None:
        if self.pending(key):
            raise RuntimeError("Publication outcome is uncertain; reconcile existing server state")
        digest = hashlib.sha256(
            json.dumps(body, sort_keys=True, allow_nan=False).encode()
        ).hexdigest()
        write_receipt(
            self.root,
            str(self.path(key).relative_to(self.root)),
            {
                "schema": 1,
                "key": key,
                "request_sha256": digest,
            },
        )

    def complete(self, key: str) -> None:
        path = self.path(key)
        if path.exists():
            path.unlink()
            sync_directory(path.parent)
