"""Immutable completion receipts; their references alone enter Temporal history."""

import fcntl
import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any

from weedz.batches.contract import artifact


def _sync(directory: Path) -> None:
    descriptor = os.open(directory, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _directory(path: Path, root: Path) -> None:
    if path == root:
        return
    _directory(path.parent, root)
    if not path.exists():
        path.mkdir(mode=0o700)
        _sync(path.parent)


def seal_file(root: Path, path: Path) -> None:
    root, path = root.resolve(), path.resolve()
    if not path.is_relative_to(root):
        raise ValueError("Durable artifact escapes owned storage")
    with path.open("rb") as stream:
        os.fsync(stream.fileno())
    directory = path.parent
    while True:
        _sync(directory)
        if directory == root:
            break
        directory = directory.parent


def _publish(path: Path, encoded: bytes) -> None:
    if path.exists():
        if path.is_symlink() or path.read_bytes() != encoded:
            raise ValueError("Existing completion receipt has conflicting content")
        return
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as stream:
        temporary = Path(stream.name)
        try:
            stream.write(encoded)
            stream.flush()
            os.fsync(stream.fileno())
            # Exclusive publication cannot replace a previously completed receipt.
            os.link(temporary, path)
        finally:
            temporary.unlink(missing_ok=True)


def write_receipt(root: Path, relative: str, document: dict[str, Any]) -> dict[str, str]:
    root = root.resolve()
    if not root.is_dir() or any((p / ".git").exists() for p in (root, *root.parents)):
        raise ValueError("Choose existing artifact storage outside Git")
    encoded = (json.dumps(document, sort_keys=True, allow_nan=False) + "\n").encode()
    if len(encoded) > 1024 * 1024:
        raise ValueError("Completion receipt exceeds its resource cap")
    reference = artifact({"path": relative, "sha256": hashlib.sha256(encoded).hexdigest()})
    path = root / relative
    if not path.resolve().is_relative_to(root):
        raise ValueError("Completion receipt escapes owned storage")
    _directory(path.parent, root)
    descriptor = os.open(path.with_suffix(".lock"), os.O_WRONLY | os.O_CREAT, 0o600)
    with os.fdopen(descriptor, "w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        _publish(path, encoded)
        seal_file(root, path)
    return reference
