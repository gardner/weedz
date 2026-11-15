"""Bounded, resumable conversion of locally cached DeepWeeds into closed Sample batches."""

import fcntl
import hashlib
import json
import os
import tempfile
import zipfile
from dataclasses import asdict
from pathlib import Path

from PIL import __version__ as PILLOW_VERSION

from weedz.contract import Sample
from weedz.deepweeds_source import (
    MAX_ARCHIVE_BYTES,
    RIGHTS,
    SourcePins,
    convert,
    inventory,
    verify,
)
from weedz.manifest import manifest_bytes
from weedz.segmentation.artifacts import durable_mkdir, sync_directory

OFFICIAL_PINS = SourcePins()


def _publish(path: Path, raw: bytes) -> None:
    """Complete bytes only; an existing different file is never overwritten."""
    if path.is_symlink():
        raise ValueError("Output contains a symlink")
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


def _json(path: Path, record: dict) -> None:
    _publish(path, json.dumps(record, sort_keys=True, allow_nan=False).encode())


def _directory(path: Path) -> None:
    if path.is_symlink():
        raise ValueError("Output contains a symlink")
    durable_mkdir(path)
    for directory in (path, *path.parents):
        sync_directory(directory)
        if not os.access(directory.parent, os.W_OK):
            break


def _closed(folder: Path, rows: list[dict[str, str]], pins: SourcePins) -> list[Sample] | None:
    if folder.is_symlink() or (folder / "images").is_symlink():
        raise ValueError("Output contains a symlink")
    ready = folder / "ready.json"
    if not ready.exists():
        return None
    manifest = folder / "samples.jsonl"
    if ready.is_symlink() or manifest.is_symlink() or ready.stat().st_size > 4096:
        raise ValueError("Invalid closed batch marker")
    if manifest.stat().st_size > 32_000_000:
        raise ValueError("Closed batch manifest exceeds byte cap")
    raw = manifest.read_bytes()
    marker = json.loads(ready.read_bytes())
    if marker != _marker(raw, len(rows), pins):
        raise ValueError("Closed batch checksum or source identity changed")
    samples = [Sample.model_validate_json(line) for line in raw.splitlines()]
    if len(samples) != len(rows):
        raise ValueError("Closed batch count changed")
    for sample, row in zip(samples, rows, strict=True):
        image = folder / "images" / Path(row["Filename"]).with_suffix(".png")
        _validate_sample(sample, row, image, pins)
    sync_directory(folder)
    return samples


def _validate_sample(sample: Sample, row: dict[str, str], image: Path, pins: SourcePins) -> None:
    if (
        sample.id != "deepweeds:" + row["Filename"]
        or sample.rights != RIGHTS
        or sample.original_label != row["Species"]
        or sample.annotations
        or sample.tasks != {"inference"}
        or sample.media.uri != str(image)
        or sample.snapshot != "DeepWeeds2019-images-sha256:" + pins.archive_sha256
        or sample.context.get("source_labels_sha256") != pins.labels_sha256
        or sample.context.get("source_image_sha256") != row["_sha256"]
        or sample.context.get("source_class_id") != row["Label"]
        or image.is_symlink()
        or image.stat().st_size > 20_000_000
        or hashlib.sha256(image.read_bytes()).hexdigest() != sample.media.sha256
    ):
        raise ValueError("Closed sample source, rights or image checksum changed")


def _marker(raw: bytes, count: int, pins: SourcePins) -> dict:
    return {
        "schema": 1,
        "count": count,
        "samples_sha256": hashlib.sha256(raw).hexdigest(),
        "source": "deepweeds",
        "source_pins": asdict(pins),
        "human_annotations": 0,
    }


def _batch(
    archive: zipfile.ZipFile, folder: Path, rows: list[dict[str, str]], pins: SourcePins
) -> list[Sample]:
    if completed := _closed(folder, rows, pins):
        return completed
    _directory(folder)
    _directory(folder / "images")
    samples = []
    for row in rows:
        target = folder / "images" / Path(row["Filename"]).with_suffix(".png")
        raw, sample = convert(archive.read(row["Filename"]), row, target, pins)
        _publish(target, raw)
        samples.append(sample)
    raw = manifest_bytes(samples)
    _publish(folder / "samples.jsonl", raw)
    _json(folder / "ready.json", _marker(raw, len(samples), pins))
    return samples


def _destination(output: Path, inputs: tuple[Path, Path]) -> Path:
    resolved = output.resolve()
    if output.is_symlink() or any(path.resolve().is_relative_to(resolved) for path in inputs):
        raise ValueError("Output must not contain source inputs")
    if any((parent / ".git").exists() for parent in (resolved, *resolved.parents)):
        raise ValueError("Dataset output must remain outside Git")
    return resolved


def _selected_checksums(archive: zipfile.ZipFile, rows: list[dict[str, str]]) -> set[str]:
    checksums: set[str] = set()
    for row in rows:
        checksum = hashlib.sha256(archive.read(row["Filename"])).hexdigest()
        if checksum in checksums:
            raise ValueError("Duplicate encoded source images")
        checksums.add(checksum)
        row["_sha256"] = checksum
    return checksums


def materialize(
    archive: Path,
    labels: Path,
    output: Path,
    *,
    limit: int,
    batch_size: int = 100,
    pins: SourcePins = OFFICIAL_PINS,
) -> dict:
    """Validate all input inventory; publish at most the explicit limit, in closed batches.

    The input archive is read in place, never extracted. Completed batches are verified and
    reused; interrupted partial batches repeat at most batch_size conversions. Input pins,
    limit and batch size cannot change in an existing output namespace.
    """
    if type(limit) is not int or not 1 <= limit <= pins.count:
        raise ValueError("Explicit limit must be within source count")
    if type(batch_size) is not int or not 1 <= batch_size <= 1000:
        raise ValueError("Batch size must be 1–1000")
    destination = _destination(output, (archive, labels))
    with archive.open("rb") as source, labels.open("rb") as metadata:
        verify(source, pins.archive_sha256, MAX_ARCHIVE_BYTES)
        verify(metadata, pins.labels_sha256, 2_000_000)
        with zipfile.ZipFile(source) as zipped:
            label_bytes = metadata.read(2_000_001)
            if (
                len(label_bytes) > 2_000_000
                or hashlib.sha256(label_bytes).hexdigest() != pins.labels_sha256
            ):
                raise ValueError("Source label checksum mismatch")
            rows = inventory(zipped, label_bytes, pins)[:limit]
            checksums = _selected_checksums(zipped, rows)
            verify(source, pins.archive_sha256, MAX_ARCHIVE_BYTES)
            identity = {
                "schema": 1,
                "pins": asdict(pins),
                "limit": limit,
                "batch_size": batch_size,
                "transform": "upright-metadata-free-rgb-png-v1",
                "pillow_version": PILLOW_VERSION,
            }
            if (
                destination.exists()
                and not (destination / "source.json").exists()
                and any(path.name != ".conversion.lock" for path in destination.iterdir())
            ):
                raise ValueError("Refusing unrelated output directory")
            _directory(destination)
            lock_path = destination / ".conversion.lock"
            if lock_path.is_symlink():
                raise ValueError("Output contains a symlink")
            with lock_path.open("a") as lock:
                fcntl.flock(lock, fcntl.LOCK_EX)
                _json(destination / "source.json", identity)
                for index in range(0, limit, batch_size):
                    folder = destination / f"batch-{index // batch_size + 1:04d}"
                    _batch(zipped, folder, rows[index : index + batch_size], pins)
                # Recheck the same opened inputs before acknowledging a complete dataset.
                verify(source, pins.archive_sha256, MAX_ARCHIVE_BYTES)
                verify(metadata, pins.labels_sha256, 2_000_000)
                summary = {
                    **identity,
                    "count": limit,
                    "batches": (limit + batch_size - 1) // batch_size,
                    "distinct_source_sha256": len(checksums),
                    "human_annotations": 0,
                }
                _json(destination / "complete.json", summary)
                return summary
