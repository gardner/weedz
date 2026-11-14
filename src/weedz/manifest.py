"""A JSONL sample manifest: one validated contract sample per line, pinned by SHA-256."""

import hashlib
import os
import secrets
from collections.abc import Iterable
from pathlib import Path

from pydantic import ValidationError

from weedz.contract import Sample


def _unique(samples: list[Sample]) -> list[Sample]:
    ids = [sample.id for sample in samples]
    if len(set(ids)) != len(ids):
        raise ValueError("Duplicate sample ids in manifest")
    return samples


def manifest_bytes(samples: Iterable[Sample]) -> bytes:
    """The exact bytes `write_manifest` writes, so a digest can be known before writing."""
    rows = _unique(list(samples))
    return "".join(sample.model_dump_json() + "\n" for sample in rows).encode("utf-8")


def write_atomic(path: Path, content: bytes) -> None:
    """Replace `path` with `content` so a reader never sees a partly written file."""
    # A unique temporary file in the same directory, so concurrent writers never share one.
    # O_EXCL keeps the temporary file unique per writer; mode 0o666 lets the kernel apply
    # the umask, so nothing reads or changes the process-wide umask.
    temporary = path.with_name(f".{path.name}.{secrets.token_hex(8)}")
    # O_BINARY (Windows only; 0 elsewhere) stops text mode turning "\n" into "\r\n",
    # which would make the file differ from any checksum of `content`.
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0)
    descriptor = os.open(temporary, flags, 0o666)
    try:
        with os.fdopen(descriptor, "wb") as out:
            out.write(content)
        temporary.replace(path)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise


def write_manifest(path: Path, samples: Iterable[Sample]) -> str:
    """Write the samples atomically and return the manifest's SHA-256."""
    content = manifest_bytes(samples)
    write_atomic(path, content)
    return hashlib.sha256(content).hexdigest()


def read_manifest(path: Path, sha256: str | None = None) -> list[Sample]:
    """Read and validate every sample, first checking the manifest's SHA-256 when given."""
    content = path.read_bytes()
    if sha256 is not None and hashlib.sha256(content).hexdigest() != sha256:
        raise ValueError(f"Manifest checksum mismatch: {path}")
    samples: list[Sample] = []
    # Split bytes on newlines only: JSON escapes them, but not U+2028, U+2029 or U+0085.
    for number, line in enumerate(content.splitlines(), start=1):
        try:
            samples.append(Sample.model_validate_json(line))
        except ValidationError as error:
            raise ValueError(f"{path} line {number}: {error}") from error
    return _unique(samples)
