"""Pinned Open Images V7 validation metadata, image cache, and frozen cohorts."""

import csv
import hashlib
import json
import os
import re
from collections import defaultdict
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import TypedDict
from urllib.error import HTTPError, URLError
from urllib.request import urlopen

from weedz.region_evaluation.geometry import Box
from weedz.validation.splits import Split, split_of

DATASET_DIR = "openimages-v7"
CLASSES = "oidv7-class-descriptions-boxable.csv"
HIERARCHY = "bbox_labels_600_hierarchy.json"
LABELS = "oidv7-val-annotations-human-imagelabels.csv"
BOXES = "validation-annotations-bbox.csv"
REQUIRED = (CLASSES, HIERARCHY, LABELS, BOXES)
METADATA_URL = "https://storage.googleapis.com/openimages"
IMAGE_URL = "https://open-images-dataset.s3.amazonaws.com/validation/{id}.jpg"
METADATA = {
    CLASSES: ("v7/" + CLASSES, "1839e0e7e84130ae281f7f67413768601b031581c0c42e7fc17527b8e2a99aa9"),
    HIERARCHY: (
        "2018_04/" + HIERARCHY,
        "a28f06e83c8378c4285d92d768ceda7568a48cac3c02994b6c346df804e7d612",
    ),
    LABELS: ("v7/" + LABELS, "92ddbdfceb3626e044df5e89100b24f6c22a79c1888a4bddd00a6f231d86d56a"),
    BOXES: ("v5/" + BOXES, "d8bbd59410af14835d7733165a7bb8a3f0213981b22dd5077b0b9f7878991ff2"),
    "classes-segmentation.txt": (
        "v7/oidv7-classes-segmentation.txt",
        "a4c7ace680f843d9dc99cb5dcec1d9b0ee55405c5aedf936985c347744401917",
    ),
    "oidv7-test-annotations-human-imagelabels.csv": (
        "v7/oidv7-test-annotations-human-imagelabels.csv",
        "917d3ca8c0a2e09d652fb3148e9264df6117bfcaccf425a60a29b23269487953",
    ),
    "validation-annotations-object-segmentation.csv": (
        "v5/validation-annotations-object-segmentation.csv",
        "a876ff7a1a68de771e668baa9886f0ca2331992cd4af5497401be41828a5de89",
    ),
    "test-annotations-object-segmentation.csv": (
        "v5/test-annotations-object-segmentation.csv",
        "32d85cd4d566bb60cc3d427e26d6c9f9670c46acddac6ced70dacbf2e603e3b1",
    ),
}
POSITIVE_BUDGET = 1500
NEGATIVE_BUDGET = 1500
SMALL_MINIMUM = 300
SIZES = ("small", "medium", "large")
POSITIVE_STRATA = (*SIZES, "group-of only", "no-box")
HUMAN_SOURCES = {"verification", "crowdsource-verification"}
IMAGE_BYTE_LIMIT = 32_000_000


def sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def write_atomic(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile(dir=path.parent, delete=False) as stream:
        temporary = Path(stream.name)
        try:
            stream.write(content)
            stream.close()
            os.replace(temporary, path)
        finally:
            temporary.unlink(missing_ok=True)


def verify_metadata(root: Path) -> dict[str, str]:
    inputs = {}
    for name, (source, expected) in METADATA.items():
        relative = Path(DATASET_DIR, "metadata", name)
        path = root / relative
        if not path.exists():
            if name not in REQUIRED:
                continue
            with urlopen(f"{METADATA_URL}/{source}", timeout=60) as response:
                content = response.read()
            if hashlib.sha256(content).hexdigest() != expected:
                raise ValueError(f"Open Images metadata checksum mismatch for {name}")
            write_atomic(path, content)
        if sha256(path) != expected:
            raise ValueError(f"Open Images metadata checksum mismatch for {name}")
        inputs[relative.as_posix()] = expected
    return inputs


class ClassNode(TypedDict):
    LabelName: str
    Subcategory: list["ClassNode"]


def _subcategories(tree: ClassNode) -> Iterator[ClassNode]:
    yield tree
    for child in tree.get("Subcategory", []):
        yield from _subcategories(child)


def vegetation_scope(path: Path, plant: str) -> set[str]:
    tree: ClassNode = json.loads(path.read_text())
    branch = next((node for node in _subcategories(tree) if node["LabelName"] == plant), None)
    if branch is None:
        raise ValueError("Plant is missing from the Open Images boxable hierarchy")
    return {node["LabelName"] for node in _subcategories(branch)}


def rows(path: Path) -> Iterator[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as stream:
        yield from csv.DictReader(stream)


def size_stratum(area: float) -> str:
    # Coordinates are decimal text; rounding avoids drift at the 1% and 10% boundaries.
    area = round(area, 14)
    if area < 0.01:
        return "small"
    return "medium" if area <= 0.10 else "large"


@dataclass(frozen=True)
class LabelBox:
    box: Box
    group: bool

    @property
    def area(self) -> float:
        left, top, right, bottom = self.box
        return (right - left) * (bottom - top)


@dataclass(frozen=True)
class Item:
    id: str
    present: bool
    stratum: str
    boxes: tuple[LabelBox, ...]


def _human_labels(path: Path, plant: str, scope: set[str]) -> tuple[set[str], set[str]]:
    positive, absent = set(), set()
    for row in rows(path):
        if row["Source"] not in HUMAN_SOURCES or row["LabelName"] not in scope:
            continue
        confidence = float(row["Confidence"])
        if confidence == 1:
            positive.add(row["ImageID"])
        elif confidence == 0 and row["LabelName"] == plant:
            absent.add(row["ImageID"])
    return positive, absent


def _vegetation_boxes(path: Path, scope: set[str]) -> tuple[dict[str, list[LabelBox]], set[str]]:
    boxes: dict[str, list[LabelBox]] = defaultdict(list)
    box_ids = set()
    for row in rows(path):
        if row["LabelName"] not in scope:
            continue
        item_id = row["ImageID"]
        box_ids.add(item_id)
        if row["IsDepiction"] == "1":
            continue
        box = (float(row["XMin"]), float(row["YMin"]), float(row["XMax"]), float(row["YMax"]))
        boxes[item_id].append(LabelBox(box, row["IsGroupOf"] == "1"))
    return boxes, box_ids


def _positive_item(item_id: str, boxes: tuple[LabelBox, ...]) -> Item:
    largest = max((label.area for label in boxes if not label.group), default=None)
    stratum = (
        size_stratum(largest) if largest is not None else "group-of only" if boxes else "no-box"
    )
    return Item(item_id, True, stratum, boxes)


def load_items(labels: Path, boxes: Path, plant: str, scope: set[str]) -> list[Item]:
    positive, absent = _human_labels(labels, plant, scope)
    vegetation_boxes, box_ids = _vegetation_boxes(boxes, scope)
    return [
        *[
            _positive_item(item_id, tuple(vegetation_boxes.get(item_id, ())))
            for item_id in positive
        ],
        *[Item(item_id, False, "verified-absent", ()) for item_id in absent - positive - box_ids],
    ]


def _sample_key(item: Item) -> bytes:
    return hashlib.sha256(f"openimages-v7-cohort-v1:{item.id}".encode()).digest()


def select_items(
    items: Sequence[Item],
    split: Split,
    *,
    positive_budget: int = POSITIVE_BUDGET,
    negative_budget: int = NEGATIVE_BUDGET,
    small_minimum: int = SMALL_MINIMUM,
    limit: int | None = None,
) -> list[Item]:
    pool = sorted((item for item in items if split_of(item.id) == split), key=_sample_key)
    positives = [item for item in pool if item.present]
    negatives = [item for item in pool if not item.present]
    small = [item for item in positives if item.stratum == "small"]
    reserved = small[: min(small_minimum, positive_budget)]
    reserved_ids = {item.id for item in reserved}
    remaining = [item for item in positives if item.id not in reserved_ids]
    selected = reserved + remaining[: positive_budget - len(reserved)]
    negatives = negatives[:negative_budget]
    if limit is None:
        return selected + negatives
    return selected[: (limit + 1) // 2] + negatives[: limit // 2]


def _fetch_image(item_id: str) -> tuple[bytes, str]:
    url = IMAGE_URL.format(id=item_id)
    for attempt in range(3):
        try:
            with urlopen(url, timeout=30) as response:
                etag = response.headers.get("ETag", "").strip('"')
                content = response.read(IMAGE_BYTE_LIMIT + 1)
        except URLError as error:
            if attempt == 2 or isinstance(error, HTTPError) and error.code < 500:
                raise
            continue
        digest = hashlib.md5(content, usedforsecurity=False).hexdigest()
        if len(content) > IMAGE_BYTE_LIMIT or digest != etag:
            raise ValueError(f"Open Images image byte budget or S3 checksum mismatch for {item_id}")
        return content, hashlib.sha256(content).hexdigest()
    raise RuntimeError(f"Open Images download retries exhausted for {item_id}")


def image_path(cache: Path, item_id: str) -> Path:
    if not re.fullmatch(r"[0-9a-f]{16}", item_id):
        raise ValueError(f"Invalid Open Images image ID {item_id!r}")
    path = cache / "images" / f"{item_id}.jpg"
    receipt = path.with_suffix(".sha256")
    if path.is_file() and receipt.is_file() and sha256(path) == receipt.read_text().strip():
        return path
    content, digest = _fetch_image(item_id)
    write_atomic(path, content)
    write_atomic(receipt, (digest + "\n").encode())
    return path
