"""Bind consumed media snapshots to their producer's portable checksum receipt."""

import hashlib
from pathlib import Path

WEB_MEDIA = (
    "web-review-interactions.webm",
    "web-reference-comparison.png",
    "web-candidate-window.png",
)


def checked_files(
    root: Path, names: tuple[str, ...], hashes: object, target: Path | None = None
) -> None:
    if not isinstance(hashes, dict):
        raise ValueError("Media checksum receipt is missing or malformed")
    for name in names:
        _checked_file(root / name, target / name if target else None, hashes.get(name))


def _checked_file(path: Path, target: Path | None, expected: object) -> None:
    if not isinstance(expected, str) or len(expected) != 64:
        raise ValueError(f"Media checksum is missing: {path.name}")
    digest = hashlib.sha256()
    try:
        with path.open("rb") as source:
            destination = target.open("xb") if target is not None else None
            try:
                while chunk := source.read(1024 * 1024):
                    digest.update(chunk)
                    if destination is not None:
                        destination.write(chunk)
            finally:
                if destination is not None:
                    destination.close()
    except OSError as error:
        raise ValueError(f"Cannot read verified media: {path.name}") from error
    if digest.hexdigest() != expected:
        raise ValueError(f"Media checksum mismatch: {path.name}")
