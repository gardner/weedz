"""Wire-version selection for meaningful sample extensions, without rewriting v1 data."""

from collections.abc import Iterable, Mapping
from typing import Any

LEGACY_SCHEMA_VERSION = 1
SCHEMA_VERSION = 2


def required_sample_version(fields: Mapping[str, Any]) -> int:
    if fields.get("completeness") or fields.get("review_history"):
        return SCHEMA_VERSION
    notes = fields.get("annotations") or ()
    if not isinstance(notes, Iterable) or isinstance(notes, (str, bytes, Mapping)):
        return LEGACY_SCHEMA_VERSION
    for note in notes:
        if isinstance(note, Mapping):
            category, mask_hash = note.get("category"), note.get("mask_sha256")
        else:
            category, mask_hash = (
                getattr(note, "category", None),
                getattr(note, "mask_sha256", None),
            )
        if category is not None or mask_hash is not None:
            return SCHEMA_VERSION
    return LEGACY_SCHEMA_VERSION


def sample_version_fields(data: object) -> object:
    if not isinstance(data, Mapping):
        return data
    fields = materialize_sample_fields(data)
    minimum = required_sample_version(fields)
    version = fields.get("schema_version", minimum)
    if type(version) is not int or version not in {LEGACY_SCHEMA_VERSION, SCHEMA_VERSION}:
        raise ValueError("Unsupported sample schema version")
    if version < minimum:
        raise ValueError("Sample schema version 1 cannot contain meaningful version 2 extensions")
    fields["schema_version"] = version
    return fields


def materialize_sample_fields(data: Mapping[str, Any]) -> dict[str, Any]:
    fields = dict(data)
    for key in ("annotations", "completeness", "review_history"):
        values = fields.get(key)
        if isinstance(values, Iterable) and not isinstance(values, (str, bytes, Mapping)):
            fields[key] = tuple(values)
    return fields
