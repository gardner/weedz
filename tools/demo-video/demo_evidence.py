"""Bind source photographs and credits to one checksum-verified snapshot manifest."""

import hashlib
import io
from pathlib import Path
from typing import Any

from PIL import Image


def photo_record(manifest: dict[str, Any], relative: str) -> dict[str, Any]:
    matches = [row for row in manifest["photos"] if row["file"] == relative]
    if len(matches) != 1:
        raise ValueError("A rendered source photo needs exactly one snapshot attribution")
    return matches[0]


def verified_photo_bytes(captures: Path, relative: str, manifest: dict[str, Any]) -> bytes:
    record = photo_record(manifest, relative)
    root = (captures / "review-snapshot").resolve()
    path = (root / relative).resolve()
    if not path.is_relative_to(root / "images") or not path.is_file():
        raise ValueError("Rendered source photo must remain inside the snapshot image cache")
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != record.get("sha256"):
        raise ValueError("Snapshot photo checksum mismatch; regenerate the documented snapshot")
    return raw


def verified_photo(captures: Path, relative: str, manifest: dict[str, Any]) -> Image.Image:
    raw = verified_photo_bytes(captures, relative, manifest)
    # Decode exactly the bytes that were checked, not a second read of a mutable path.
    with Image.open(io.BytesIO(raw)) as source:
        return source.convert("RGB")
