"""Explicit authorization for one absent legacy display field; never a task mutation."""

import hashlib
import json
import os
import re
import stat
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from weedz.annotation.credits import photo_credit
from weedz.batches.storage import PUBLIC
from weedz.contract import Sample, require_task
from weedz.segmentation.artifacts import digest

SHA256 = re.compile(r"[0-9a-f]{64}")
ENTRY_FIELDS = {
    "task_id",
    "external_id",
    "sample_id",
    "source",
    "source_id",
    "image_sha256",
    "data_sha256",
    "meta_sha256",
}


def _reference(reference: dict) -> tuple[Path, str]:
    if not isinstance(reference, dict) or set(reference) != {"path", "sha256"}:
        raise ValueError("Legacy authorization requires an explicit file/SHA reference")
    raw_path, expected = reference["path"], reference["sha256"]
    if (
        not isinstance(raw_path, str)
        or not isinstance(expected, str)
        or not SHA256.fullmatch(expected)
    ):
        raise ValueError("Invalid legacy authorization reference")
    path = Path(raw_path)
    if not path.is_absolute() or any((p / ".git").exists() for p in (path.parent, *path.parents)):
        raise ValueError("Legacy authorization files must be absolute and outside Git")
    return path, expected


def _read(reference: dict, maximum: int, *, private: bool = False) -> tuple[dict, str]:
    path, expected = _reference(reference)
    try:
        descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        with os.fdopen(descriptor, "rb") as stream:
            info = os.fstat(stream.fileno())
            if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid():
                raise ValueError("Legacy authorization requires an owned regular file")
            if private and info.st_mode & 0o077:
                raise ValueError("Legacy allowlist must be owner-private (0600)")
            raw = stream.read(maximum + 1)
    except OSError as error:
        raise ValueError("Cannot read legacy authorization file") from error
    if len(raw) > maximum or hashlib.sha256(raw).hexdigest() != expected:
        raise ValueError("Legacy authorization checksum mismatch or byte cap exceeded")
    document = json.loads(raw)
    if not isinstance(document, dict):
        raise ValueError("Legacy authorization must be a JSON object")
    return document, expected


def _entry(row: Any) -> None:
    if not isinstance(row, dict) or set(row) != ENTRY_FIELDS:
        raise ValueError("Legacy task entry has missing or unsupported fields")
    identifier = row["task_id"]
    if type(identifier) is not int or identifier <= 0:
        raise ValueError("Legacy task IDs must be positive and unique")
    for key in ("external_id", "image_sha256", "data_sha256", "meta_sha256"):
        if not isinstance(row[key], str) or not SHA256.fullmatch(row[key]):
            raise ValueError("Legacy task entry requires complete SHA256 identities")
    if any(
        not isinstance(row[key], str) or not row[key]
        for key in ("sample_id", "source", "source_id")
    ):
        raise ValueError("Legacy task source identity is incomplete")


def _entries(rows: Any) -> dict[str, dict]:
    if not isinstance(rows, list) or not 1 <= len(rows) <= 1000:
        raise ValueError("Legacy allowlist requires 1–1000 task entries")
    result, identifiers = {}, set()
    for row in rows:
        _entry(row)
        identifier = row["task_id"]
        if identifier in identifiers:
            raise ValueError("Legacy task IDs must be unique")
        if row["external_id"] in result:
            raise ValueError("Legacy external identities must be unique")
        identifiers.add(identifier)
        result[row["external_id"]] = row
    return result


def _source_sample(row: dict, key: str, expected: dict) -> Sample:
    sample = Sample.model_validate(row["sample"])
    require_task(sample, "inference")
    fields = {
        "sample_id": sample.id,
        "source": sample.source,
        "source_id": sample.source_id,
        "image_sha256": sample.media.sha256,
    }
    canonical = hashlib.sha256(f"{sample.id}:{sample.media.sha256}".encode()).hexdigest()
    if key != canonical or any(expected[name] != value for name, value in fields.items()):
        raise ValueError("Legacy identity differs from original source provenance")
    if sample.rights.consent is not None or any(
        value.lower() not in PUBLIC
        for value in (sample.rights.media_license, sample.rights.metadata_license)
    ):
        raise ValueError("Legacy compatibility cannot expand the public source-rights policy")
    return sample


def _source_samples(provenance: dict, entries: dict[str, dict]) -> dict[str, Sample]:
    rows = provenance.get("photos")
    if provenance.get("schema_version") != 1 or not isinstance(rows, list) or len(rows) > 1000:
        raise ValueError("Use the original bounded photo-export provenance")
    selected = {}
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("Malformed original photo provenance")
        key = row.get("external_id")
        if key not in entries:
            continue
        if key in selected:
            raise ValueError("Original provenance has duplicate selected identities")
        sample = _source_sample(row, key, entries[key])
        selected[key] = sample
    if set(selected) != set(entries):
        raise ValueError("Legacy entry is missing from the original source provenance")
    return selected


@dataclass(frozen=True)
class LegacyIdentities:
    sha256: str
    provenance_sha256: str
    entries: dict[str, dict]
    samples: dict[str, Sample]

    def approve(self, current: dict, expected: dict) -> int:
        key = expected["meta"]["external_id"]
        entry, sample = self.entries.get(key), self.samples.get(key)
        if entry is None or sample is None:
            raise ValueError("Missing dataset field has no legacy authorization")
        data, meta = current["data"], current.get("meta")
        if "source_dataset" in data or not isinstance(meta, dict):
            raise ValueError("Legacy authorization applies only to an absent dataset field")
        if (
            type(current["id"]) is not int
            or current["id"] != entry["task_id"]
            or meta.get("external_id") != key
            or digest(data) != entry["data_sha256"]
            or digest(meta) != entry["meta_sha256"]
        ):
            raise ValueError("Existing legacy task identity/data/meta changed")
        if (
            expected["data"]["source_dataset"] != sample.source
            or expected["meta"]["image_sha256"] != sample.media.sha256
        ):
            raise ValueError("Canonical publication differs from the legacy source")
        rights = sample.rights
        if expected["data"]["photo_credit"] != photo_credit(
            rights.attribution, rights.media_license, rights.metadata_license, rights.license_source
        ):
            raise ValueError("Legacy source rights differ from canonical visible credit")
        return entry["task_id"]


def load_legacy_identities(reference: dict | None, project: int) -> LegacyIdentities | None:
    if reference is None:
        return None
    document, sha = _read(reference, 1024 * 1024, private=True)
    if (
        set(document) != {"schema", "project_id", "provenance", "tasks"}
        or type(document["schema"]) is not int
        or document["schema"] != 1
        or type(document["project_id"]) is not int
        or document["project_id"] != project
    ):
        raise ValueError("Legacy allowlist schema/project does not match publication")
    entries = _entries(document["tasks"])
    provenance, source_sha = _read(document["provenance"], 128_000_000)
    return LegacyIdentities(sha, source_sha, entries, _source_samples(provenance, entries))
