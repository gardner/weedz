"""Pinned official DeepWeeds inventory and credited inference-only sample conversion."""

import csv
import hashlib
import io
import re
import stat
import zipfile
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO

from PIL import Image, ImageOps

from weedz.contract import Media, Rights, Sample

REPOSITORY = "https://github.com/AlexOlsen/DeepWeeds"
REVISION = "da084f62bcd1a2b0afeb8b81f1a27be3186391a1"
ARCHIVE_SHA256 = "0961f63c01b997bfab1559ad09e99c0e8130617fd96a8b92fdc09940e01b0ce8"
LABELS_SHA256 = "6fb95b89fd9d384f94e185a5cab6c5da7c987649399c90618ecc60acfb0112eb"
SPECIES = (
    "Chinee apple",
    "Lantana",
    "Parkinsonia",
    "Parthenium",
    "Prickly acacia",
    "Rubber vine",
    "Siam weed",
    "Snake weed",
    "Negative",
)
MAX_IMAGE_BYTES = 20_000_000
MAX_PIXELS = 40_000_000
MAX_ARCHIVE_BYTES = 1_000_000_000
RIGHTS = Rights(
    media_license="CC-BY-4.0",
    metadata_license="CC-BY-4.0",
    attribution="Alex Olsen et al. (2019), DeepWeeds, Scientific Reports 9:2058, CC BY 4.0",
    license_source=REPOSITORY + "/blob/" + REVISION + "/README.md",
)


@dataclass(frozen=True)
class SourcePins:
    """Explicit input identity; CLI uses the verified official release pins exclusively."""

    archive_sha256: str = ARCHIVE_SHA256
    labels_sha256: str = LABELS_SHA256
    count: int = 17509

    def __post_init__(self) -> None:
        if (
            not all(
                re.fullmatch(r"[0-9a-f]{64}", value)
                for value in (self.archive_sha256, self.labels_sha256)
            )
            or not 1 <= self.count <= 17509
        ):
            raise ValueError("Invalid source pins")


def verify(stream: BinaryIO, expected: str, maximum: int) -> None:
    stream.seek(0)
    checksum, total = hashlib.sha256(), 0
    while raw := stream.read(1024 * 1024):
        total += len(raw)
        if total > maximum:
            raise ValueError("Source exceeds byte cap")
        checksum.update(raw)
    if checksum.hexdigest() != expected:
        raise ValueError("Source checksum mismatch")
    stream.seek(0)


def filename(name: str) -> bool:
    return re.fullmatch(r"[0-9]{8}-[0-9]{6}-[0-9]\.jpg", name) is not None


def _label_rows(labels: bytes, pins: SourcePins) -> list[dict[str, str]]:
    reader = csv.DictReader(io.StringIO(labels.decode("utf-8-sig")))
    if reader.fieldnames != ["Filename", "Label", "Species"]:
        raise ValueError("Unexpected authoritative label columns")
    rows = list(reader)
    if len(rows) != pins.count:
        raise ValueError("Authoritative label count mismatch")
    for row in rows:
        label, name = row.get("Label", ""), row.get("Filename", "")
        if not filename(name) or label not in {str(i) for i in range(9)}:
            raise ValueError("Invalid source label or filename")
        if row.get("Species") != SPECIES[int(label)] or None in row:
            raise ValueError("Authoritative species label mismatch")
    if len({row["Filename"] for row in rows}) != len(rows):
        raise ValueError("Duplicate source label filename")
    return rows


def _members(archive: zipfile.ZipFile, names: set[str], pins: SourcePins) -> None:
    members = archive.infolist()
    if len(members) != pins.count:
        raise ValueError("Archive member count mismatch")
    for member in members:
        mode = member.external_attr >> 16
        if not filename(member.filename) or member.orig_filename != member.filename:
            raise ValueError("Unsafe archive member filename")
        if (
            stat.S_ISLNK(mode)
            or member.flag_bits & 1
            or not 0 < member.file_size <= MAX_IMAGE_BYTES
        ):
            raise ValueError("Unsafe archive member type or size")
    if len({member.filename for member in members}) != len(members):
        raise ValueError("Duplicate archive member")
    if {member.filename for member in members} != names:
        raise ValueError("Archive members differ from authoritative labels")
    if sum(member.file_size for member in members) > 2_000_000_000:
        raise ValueError("Archive decoded byte cap exceeded")


def inventory(archive: zipfile.ZipFile, labels: bytes, pins: SourcePins) -> list[dict[str, str]]:
    rows = _label_rows(labels, pins)
    _members(archive, {row["Filename"] for row in rows}, pins)
    groups: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        groups[row["Label"]].append(row)
    # Same deterministic class round-robin as the original operational conversion.
    return [
        group[index]
        for index in range(max(map(len, groups.values())))
        for _, group in sorted(groups.items())
        if index < len(group)
    ]


def convert(
    raw: bytes, row: dict[str, str], target: Path, pins: SourcePins
) -> tuple[bytes, Sample]:
    if len(raw) > MAX_IMAGE_BYTES or hashlib.sha256(raw).hexdigest() != row["_sha256"]:
        raise ValueError("Source image bytes changed after inventory validation")
    with Image.open(io.BytesIO(raw)) as original:
        if original.format != "JPEG" or original.width * original.height > MAX_PIXELS:
            raise ValueError("Invalid source image format or pixel cap")
        upright = ImageOps.exif_transpose(original).convert("RGB")
        clean = Image.new("RGB", upright.size)
        clean.paste(upright)
    encoded = io.BytesIO()
    clean.save(encoded, format="PNG")
    png = encoded.getvalue()
    if len(png) > MAX_IMAGE_BYTES:
        raise ValueError("Canonical image exceeds byte cap")
    name = row["Filename"]
    sample = Sample(
        id=f"deepweeds:{name}",
        source="deepweeds",
        source_id=name,
        snapshot="DeepWeeds2019-images-sha256:" + pins.archive_sha256,
        rights=RIGHTS,
        media=Media(
            uri=str(target),
            sha256=hashlib.sha256(png).hexdigest(),
            width=clean.width,
            height=clean.height,
            format="PNG",
        ),
        original_label=row["Species"],
        tasks=frozenset({"inference"}),
        context={
            "source_url": "https://doi.org/10.1038/s41598-018-38343-3",
            "source_image_sha256": hashlib.sha256(raw).hexdigest(),
            "source_filename": name,
            "source_class_id": row["Label"],
            "source_labels_sha256": pins.labels_sha256,
            "source_label_meaning": "Original DeepWeeds image class; not independently verified "
            "background labels, mask ground truth or NZ watchlist coverage",
            "modification": "EXIF-upright RGB metadata-free lossless PNG",
        },
    )
    return png, sample
