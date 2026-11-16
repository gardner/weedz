"""Validate final referenced assets separately from deliberately revised metadata."""

import hashlib
from collections.abc import Iterable, Mapping

from weedz.contract import Sample
from weedz.review_values import FrozenJson


def _add(references: dict[str, str | None], uri: object, checksum: object) -> None:
    if not isinstance(uri, str) or (checksum is not None and not isinstance(checksum, str)):
        raise ValueError("Invalid retained asset reference")
    previous = references.get(uri)
    if previous is not None and checksum is not None and previous != checksum:
        raise ValueError("Conflicting asset checksums for one path")
    references[uri] = checksum if checksum is not None else previous


def asset_references(samples: Iterable[Sample]) -> dict[str, str | None]:
    references: dict[str, str | None] = {}
    for sample in samples:
        _add(references, sample.media.uri, sample.media.sha256)
        for note in sample.annotations:
            if note.mask_uri is not None:
                _add(references, note.mask_uri, note.mask_sha256)
        for event in sample.review_history:
            _historical_references(references, event.payload)
        if "assessed_mask_uri" in sample.context:
            _add(
                references,
                sample.context["assessed_mask_uri"],
                sample.context.get("assessed_mask_sha256"),
            )
    return references


def _mask_reference(references: dict[str, str | None], row: object) -> None:
    if isinstance(row, Mapping) and row.get("mask_uri") is not None:
        _add(references, row["mask_uri"], row.get("mask_sha256"))


def _historical_references(
    references: dict[str, str | None], payload: Mapping[str, FrozenJson]
) -> None:
    _mask_reference(references, payload.get("claim"))
    rows = payload.get("annotations", ())
    if isinstance(rows, tuple):
        for row in rows:
            _mask_reference(references, row)


def check_assets(
    samples: Iterable[Sample], files: dict[str, bytes], original: dict[str, bytes] | None = None
) -> None:
    for name, expected in asset_references(samples).items():
        raw = files.get(name)
        if raw is None or (original is not None and raw != original.get(name)):
            raise ValueError(
                "Generated metadata conflicts with a retained asset or asset is missing"
            )
        if expected is not None and hashlib.sha256(raw).hexdigest() != expected:
            raise ValueError("Final asset bytes differ from their declared checksum")


def add_snapshot(files: dict[str, bytes], name: str, raw: bytes) -> None:
    if name in files and files[name] != raw:
        raise ValueError("Retained file conflicts with an immutable snapshot")
    files[name] = raw


def check_source_files(original: dict[str, bytes], retained: dict[str, bytes]) -> None:
    regenerated = {"samples.jsonl", "private/provenance.json"}
    if any(retained.get(name) != raw for name, raw in original.items() if name not in regenerated):
        raise ValueError("Previous import changed or removed a retained source file")
