"""Close a release over exact local media, current masks and historical review masks."""

import hashlib
from collections.abc import Iterable, Mapping
from pathlib import Path, PurePosixPath

from pydantic import TypeAdapter

from weedz.contract import Sample, Sha256
from weedz.release_models import MANIFEST, RELEASE
from weedz.review_values import FrozenJson

MAX_ASSET_BYTES = 160_000_000
MAX_RELEASE_BYTES = 16_000_000_000
DIGEST = TypeAdapter(Sha256)


def asset_path(root: Path, uri: str) -> Path:
    relative = PurePosixPath(uri)
    invalid = (
        relative.is_absolute(),
        ".." in relative.parts,
        relative.as_posix() != uri,
        not relative.parts,
        any(mark in uri for mark in ("\\", ":", "?", "#")),
        next(iter(relative.parts), "") in {MANIFEST, RELEASE},
    )
    if any(invalid):
        raise ValueError(f"Unsafe release asset path: {uri}")
    path = root / relative
    if path.is_symlink() or not path.resolve().is_relative_to(root.resolve()):
        raise ValueError(f"Unsafe release asset path: {uri}")
    return path


def _add(assets: dict[str, str], uri: object, sha: object) -> None:
    if not isinstance(uri, str) or not isinstance(sha, str):
        raise ValueError("Every closed release asset needs its URI and SHA-256")
    # Reuse the contract's digest validation rather than accepting malformed references.
    digest = DIGEST.validate_python(sha)
    previous = assets.setdefault(uri, digest)
    if previous != digest:
        raise ValueError(f"Conflicting release asset checksums for {uri}")


def _historical_masks(payload: Mapping[str, FrozenJson], assets: dict[str, str]) -> None:
    rows = payload.get("annotations")
    if not isinstance(rows, tuple):
        return
    for row in rows:
        if isinstance(row, Mapping) and row.get("mask_uri") is not None:
            _add(assets, row["mask_uri"], row.get("mask_sha256"))


def collect_assets(samples: Iterable[Sample]) -> dict[str, str]:
    """Only supported references travel; private exports and arbitrary context do not."""
    assets: dict[str, str] = {}
    for sample in samples:
        _add(assets, sample.media.uri, sample.media.sha256)
        for note in sample.annotations:
            if note.mask_uri is not None:
                _add(assets, note.mask_uri, note.mask_sha256)
        for event in sample.review_history:
            _historical_masks(event.payload, assets)
        if "assessed_mask_uri" in sample.context:
            _add(
                assets,
                sample.context["assessed_mask_uri"],
                sample.context.get("assessed_mask_sha256"),
            )
    return dict(sorted(assets.items()))


def _transfer(source: Path, target: Path | None, expected: str) -> int:
    size, digest = 0, hashlib.sha256()
    if target is not None:
        target.parent.mkdir(parents=True, exist_ok=True)
    with source.open("rb") as incoming:
        output = target.open("xb") if target is not None else None
        try:
            while chunk := incoming.read(1024 * 1024):
                size += len(chunk)
                if size > MAX_ASSET_BYTES:
                    raise ValueError(f"Release asset exceeds the byte budget: {source}")
                digest.update(chunk)
                if output is not None:
                    output.write(chunk)
        finally:
            if output is not None:
                output.close()
    if digest.hexdigest() != expected:
        raise ValueError(f"Release asset checksum mismatch: {source}")
    return size


def verify_assets(root: Path, assets: Mapping[str, str], destination: Path | None = None) -> None:
    """Hash the captured bytes, optionally copying exactly those bytes into staging."""
    total = 0
    for uri, expected in assets.items():
        target = asset_path(destination, uri) if destination is not None else None
        total += _transfer(asset_path(root, uri), target, expected)
        if total > MAX_RELEASE_BYTES:
            raise ValueError("Release assets exceed the total byte budget")
