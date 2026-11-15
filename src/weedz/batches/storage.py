"""Read a closed canonical batch once; hashes bind the exact bytes decoded below."""

import hashlib
import io
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from PIL import Image

from weedz.batches.contract import artifact
from weedz.contract import Sample, require_task

PUBLIC = frozenset({"cc0", "cc0-1.0", "cc-by", "cc-by-3.0", "cc-by-4.0"})


@dataclass(frozen=True)
class ClosedBatch:
    manifest: Path
    sha256: str
    samples: tuple[Sample, ...]


def _read(path: Path, root: Path, maximum: int) -> bytes:
    resolved = path.resolve()
    if not resolved.is_relative_to(root.resolve()) or path.is_symlink():
        raise ValueError("Batch artifact escapes owned storage or is a symbolic link")
    if not resolved.is_file() or resolved.stat().st_size > maximum:
        raise ValueError("Batch artifact is missing or exceeds its resource cap")
    with resolved.open("rb") as stream:
        encoded = stream.read(maximum + 1)
    if len(encoded) > maximum:
        raise ValueError("Batch artifact exceeds its resource cap")
    return encoded


def read_artifact(root: Path, reference: dict, maximum: int) -> bytes:
    pinned = artifact(reference)
    encoded = _read(root / pinned["path"], root, maximum)
    if hashlib.sha256(encoded).hexdigest() != pinned["sha256"]:
        raise ValueError("Batch artifact checksum mismatch")
    return encoded


def _media(sample: Sample, folder: Path) -> None:
    require_task(sample, "inference")
    rights = sample.rights
    if (
        rights.consent is not None
        or rights.media_license.lower() not in PUBLIC
        or rights.metadata_license.lower() not in PUBLIC
    ):
        raise ValueError("Canonical annotation batches require public CC0/CC BY rights")
    encoded = _read(folder / sample.media.uri, folder, 160 * 1024 * 1024)
    if hashlib.sha256(encoded).hexdigest() != sample.media.sha256:
        raise ValueError("Canonical image checksum mismatch")
    with Image.open(io.BytesIO(encoded)) as image:
        if (
            image.format != "PNG"
            or image.mode != "RGB"
            or image.info
            or image.size != (sample.media.width, sample.media.height)
            or image.width * image.height > 40_000_000
            or image.getexif()
        ):
            raise ValueError("Canonical pixels must be bounded metadata-free upright RGB PNG")
        image.load()


def _samples(encoded: bytes) -> tuple[Sample, ...]:
    rows = tuple(Sample.model_validate_json(line) for line in encoded.splitlines())
    if not 1 <= len(rows) <= 1000 or len({sample.id for sample in rows}) != len(rows):
        raise ValueError("Closed batch requires 1–1000 distinct sample identities")
    return rows


def validate_closed_batch(root: Path, manifest: dict, ready: dict) -> ClosedBatch:
    manifest_ref = artifact(manifest)
    encoded = read_artifact(root, manifest_ref, 32 * 1024 * 1024)
    readiness: Any = json.loads(read_artifact(root, ready, 64 * 1024))
    if (
        not isinstance(readiness, dict)
        or readiness.get("schema") != 1
        or readiness.get("samples_sha256") != manifest_ref["sha256"]
    ):
        raise ValueError("Closed batch readiness does not bind this exact manifest")
    samples = _samples(encoded)
    if type(readiness.get("count")) is not int or readiness["count"] != len(samples):
        raise ValueError("Closed readiness count differs from the manifest")
    path = (root / manifest_ref["path"]).resolve()
    for sample in samples:
        _media(sample, path.parent)
    return ClosedBatch(path, manifest_ref["sha256"], samples)
