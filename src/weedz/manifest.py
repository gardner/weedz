"""A JSONL sample manifest: one validated contract sample per line, pinned by SHA-256."""

import hashlib
from collections.abc import Iterable
from pathlib import Path

from pydantic import ValidationError

from weedz.contract import Sample


def _unique(samples: list[Sample]) -> list[Sample]:
    ids = [sample.id for sample in samples]
    if len(set(ids)) != len(ids):
        raise ValueError("Duplicate sample ids in manifest")
    return samples


def write_manifest(path: Path, samples: Iterable[Sample]) -> str:
    """Write the samples atomically and return the manifest's SHA-256."""
    rows = _unique(list(samples))
    content = "".join(sample.model_dump_json() + "\n" for sample in rows).encode("utf-8")
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_bytes(content)
    temporary.replace(path)
    return hashlib.sha256(content).hexdigest()


def read_manifest(path: Path, sha256: str | None = None) -> list[Sample]:
    """Read and validate every sample, first checking the manifest's SHA-256 when given."""
    content = path.read_bytes()
    if sha256 is not None and hashlib.sha256(content).hexdigest() != sha256:
        raise ValueError(f"Manifest checksum mismatch: {path}")
    samples: list[Sample] = []
    for number, line in enumerate(content.decode("utf-8").splitlines(), start=1):
        try:
            samples.append(Sample.model_validate_json(line))
        except ValidationError as error:
            raise ValueError(f"{path} line {number}: {error}") from error
    return _unique(samples)
