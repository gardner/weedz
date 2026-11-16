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
from weedz.rights_profiles import (
    PUBLIC_PROFILE,
    RightsProfile,
    parse_rights_profile,
    require_rights,
)


@dataclass(frozen=True)
class ClosedBatch:
    manifest: Path
    sha256: str
    samples: tuple[Sample, ...]
    rights_profile: RightsProfile = PUBLIC_PROFILE


def read_owned_file(path: Path, root: Path, maximum: int) -> bytes:
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
    encoded = read_owned_file(root / pinned["path"], root, maximum)
    if hashlib.sha256(encoded).hexdigest() != pinned["sha256"]:
        raise ValueError("Batch artifact checksum mismatch")
    return encoded


def _media(sample: Sample, folder: Path, rights_profile: RightsProfile) -> None:
    require_task(sample, "inference")
    require_rights(sample, rights_profile)
    encoded = read_owned_file(folder / sample.media.uri, folder, 160 * 1024 * 1024)
    if hashlib.sha256(encoded).hexdigest() != sample.media.sha256:
        raise ValueError("Canonical image checksum mismatch")
    with Image.open(io.BytesIO(encoded)) as image:
        if (
            image.format != "PNG"
            or image.mode != "RGB"
            or image.size != (sample.media.width, sample.media.height)
            or image.width * image.height > 40_000_000
        ):
            raise ValueError("Canonical pixels must be bounded metadata-free upright RGB PNG")
        image.load()
        if image.info or image.getexif():
            raise ValueError("Canonical pixels must be metadata-free upright RGB PNG")


def _samples(encoded: bytes) -> tuple[Sample, ...]:
    rows = tuple(Sample.model_validate_json(line) for line in encoded.splitlines())
    if not 1 <= len(rows) <= 1000 or len({sample.id for sample in rows}) != len(rows):
        raise ValueError("Closed batch requires 1–1000 distinct sample identities")
    return rows


def validate_closed_batch(
    root: Path, manifest: dict, ready: dict, *, rights_profile: RightsProfile = PUBLIC_PROFILE
) -> ClosedBatch:
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
    selected = parse_rights_profile(rights_profile)
    if parse_rights_profile(readiness.get("rights_profile", PUBLIC_PROFILE)) != selected:
        raise ValueError("Closed readiness rights profile differs from the requested profile")
    if type(readiness.get("count")) is not int or readiness["count"] != len(samples):
        raise ValueError("Closed readiness count differs from the manifest")
    path = (root / manifest_ref["path"]).resolve()
    for sample in samples:
        _media(sample, path.parent, selected)
    return ClosedBatch(path, manifest_ref["sha256"], samples, selected)
