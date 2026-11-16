"""Exclusive, resumable publication of closed source-labelled assets."""

import hashlib
import json
import os
import subprocess
import tempfile
from pathlib import Path

from weedz.contract import Sample
from weedz.manifest import manifest_bytes
from weedz.segmentation.artifacts import durable_mkdir, sync_directory


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def publish(path: Path, raw: bytes) -> None:
    if any(part.is_symlink() for part in (path, *path.parents)):
        raise ValueError("Output contains a symlink")
    durable_mkdir(path.parent)
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as stream:
        temporary = Path(stream.name)
        try:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
            try:
                os.link(temporary, path)
            except FileExistsError:
                if path.read_bytes() != raw:
                    raise ValueError("Existing output differs from pinned conversion") from None
            sync_directory(path.parent)
        finally:
            temporary.unlink(missing_ok=True)


def json_bytes(record: dict) -> bytes:
    return json.dumps(record, sort_keys=True, allow_nan=False).encode() + b"\n"


def close_batch(output: Path, samples: list[Sample], provenance: dict) -> str:
    raw = manifest_bytes(samples)
    publish(output / "samples.jsonl", raw)
    publish(output / "provenance.json", json_bytes(provenance))
    publish(
        output / "ready.json",
        json_bytes(
            {
                "schema_version": 1,
                "count": len(samples),
                "manifest_sha256": digest(raw),
                "provenance_sha256": digest(json_bytes(provenance)),
            }
        ),
    )
    return digest(raw)


def output_namespace(output: Path, source: Path) -> Path:
    resolved = output.resolve()
    original = source.resolve()
    if resolved == original or resolved in original.parents or original in resolved.parents:
        raise ValueError("Source and output namespaces must be independent")
    parent = resolved
    while not parent.exists():
        parent = parent.parent
    environment = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
    environment.update(LC_ALL="C", LANGUAGE="C")
    result = subprocess.run(
        ["git", "-C", str(parent), "rev-parse", "--is-inside-work-tree"],
        capture_output=True,
        text=True,
        check=False,
        env=environment,
    )
    if result.returncode == 0 or "not a git repository" not in result.stderr:
        raise ValueError("Dataset outputs must be outside Git worktrees")
    return resolved
