"""Pinned COCO-Stuff val2017 labels, instances and image cache."""

import fcntl
import hashlib
import json
import os
import shutil
import tempfile
import zlib
from collections import defaultdict
from collections.abc import Iterable, Iterator
from contextlib import ExitStack, contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO, Literal, TypedDict
from zipfile import ZipFile

import httpx
import numpy as np
from numpy.typing import NDArray
from PIL import Image
from pycocotools import mask as coco_mask

from weedz.provenance import checksum
from weedz.validation.registry import RunContext
from weedz.validation.splits import Split, split_of

type BoolMask = NDArray[np.bool_]
type SizeStratum = Literal["tiny", "small", "medium", "large"]
type Stratum = Literal["tiny", "small", "medium", "large", "negative", "unassessable"]

VEGETATION = frozenset(
    {
        "tree",
        "bush",
        "branch",
        "leaves",
        "grass",
        "moss",
        "straw",
        "plant-other",
        "flower",
        "potted plant",
    }
)
SIZE_STRATA: tuple[SizeStratum, ...] = ("tiny", "small", "medium", "large")
SIZE_THRESHOLDS: tuple[tuple[SizeStratum, float], ...] = (
    ("tiny", 0.005),
    ("small", 0.02),
    ("medium", 0.10),
)
VOID_TOLERANCE = 0.02
COCO = "https://s3.amazonaws.com/images.cocodataset.org"
STUFF = "https://calvin-vision.net/wp-content/uploads/data/cocostuffdataset"
LABELS = (
    "https://raw.githubusercontent.com/nightrome/cocostuff/5ca37b5a352cf8a4cd1fa39eaf5e2e36c00595db"
)
INSTANCE_MEMBER = "annotations/instances_val2017.json"


@dataclass(frozen=True)
class Download:
    url: str
    sha256: str

    @property
    def name(self) -> str:
        return self.url.rsplit("/", 1)[1]


LABEL_FILE = Download(
    f"{LABELS}/labels.txt",
    "53c59b920927b215690b4ba5aef4ed4794e5e4b278f9e67d7e633ddbfad9b830",
)
PIXEL_ARCHIVE = Download(
    f"{STUFF}/stuffthingmaps_trainval2017.zip",
    "da7f213d6a581bd6912a957573d7b4e5061de0d41f733bb27249b0fa981239d7",
)
IMAGE_ARCHIVE = Download(
    f"{COCO}/zips/val2017.zip", "4f7e2ccb2866ec5041993c9cf2a952bbed69647b115d0f74da7ce8f4bef82f05"
)
INSTANCE_ARCHIVE = Download(
    f"{COCO}/annotations/annotations_trainval2017.zip",
    "113a836d90195ee1f884e704da6304dfaaecff1f023f49b6ca93c4aaae470268",
)


def relative_path(path: Path, data_root: Path) -> str:
    return os.path.relpath(path.absolute(), data_root.absolute())


@contextmanager
def atomic_file(path: Path) -> Iterator[BinaryIO]:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, name = tempfile.mkstemp(dir=path.parent)
    temporary = Path(name)
    try:
        with os.fdopen(descriptor, "wb") as file:
            yield file
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def _transfer(url: str, partial: Path) -> None:
    offset = partial.stat().st_size if partial.exists() else 0
    headers = {"Accept-Encoding": "identity"}
    if offset:
        headers["Range"] = f"bytes={offset}-"
    with httpx.stream("GET", url, headers=headers, follow_redirects=True, timeout=60) as response:
        if response.status_code == 416:
            partial.unlink()
        response.raise_for_status()
        if response.status_code == 206 and not response.headers.get("Content-Range", "").startswith(
            f"bytes {offset}-"
        ):
            raise ValueError(f"Unexpected download range for {url}")
        with partial.open("ab" if response.status_code == 206 else "wb") as output:
            for chunk in response.iter_raw(1024 * 1024):
                output.write(chunk)


def verified_download(source: Download, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.with_suffix(path.suffix + ".lock").open("ab") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if path.exists():
            if checksum(path) != source.sha256:
                raise ValueError(f"Checksum mismatch for {path}")
            return path
        partial = path.with_suffix(path.suffix + ".part")
        if not partial.exists() or checksum(partial) != source.sha256:
            _transfer(source.url, partial)
        if checksum(partial) != source.sha256:
            partial.unlink()
            raise ValueError(f"Checksum mismatch for {source.url}")
        partial.replace(path)
        return path


def parse_labels(text: str) -> frozenset[int]:
    """Translate publisher label IDs to indexed PNG values."""
    labels = {
        name.strip(): int(index)
        for index, name in (line.split(":", 1) for line in text.splitlines())
    }
    if labels.get("unlabeled") != 0 or labels.get("person") != 1:
        raise ValueError("Unexpected COCO-Stuff label indexing")
    return frozenset(labels[name] - 1 for name in VEGETATION.intersection(labels))


def vegetation_stratum(pixels: int, total: int) -> SizeStratum:
    for name, maximum in SIZE_THRESHOLDS:
        if pixels <= maximum * total:
            return name
    return "large"


@dataclass(frozen=True)
class Masks:
    vegetation: BoolMask
    void: BoolMask

    @property
    def stratum(self) -> Stratum:
        pixels = int(np.count_nonzero(self.vegetation))
        if pixels:
            return vegetation_stratum(pixels, self.vegetation.size)
        return "negative" if self.void.mean() <= VOID_TOLERANCE else "unassessable"


def label_masks(pixels: NDArray[np.uint8], vegetation_ids: frozenset[int]) -> Masks:
    if pixels.ndim != 2 or not pixels.size or np.any((pixels > 181) & (pixels != 255)):
        raise ValueError("Expected indexed COCO-Stuff PNG labels in 0–181 or 255")
    return Masks(np.isin(pixels, tuple(vegetation_ids)), pixels == 255)


@dataclass(frozen=True)
class ImageItem:
    source_id: str
    image_member: str
    pixel_member: str

    @property
    def split(self) -> Split:
        return split_of(self.source_id)


class Instance(TypedDict):
    image_id: int
    category_id: int
    iscrowd: int
    segmentation: list[list[float]] | dict[str, object]


def potted_instances(annotations: Iterable[Instance], category: int) -> dict[str, list[Instance]]:
    instances: dict[str, list[Instance]] = defaultdict(list)
    for instance in annotations:
        if instance["category_id"] == category and not instance["iscrowd"]:
            instances[str(instance["image_id"])].append(instance)
    return dict(instances)


def instance_mask(instance: Instance, shape: tuple[int, int]) -> BoolMask:
    height, width = shape
    polygons = instance["segmentation"]
    if not isinstance(polygons, list):
        raise ValueError("Expected a polygon for a non-crowd COCO instance")
    # COCO's frPyObjects supports float polygon lists even though its stub omits them.
    encoded = coco_mask.frPyObjects(  # pyright: ignore[reportCallIssue]
        polygons,  # pyright: ignore[reportArgumentType]
        height,
        width,
    )
    return np.asarray(coco_mask.decode(coco_mask.merge(encoded)), dtype=bool)


@dataclass
class Dataset:
    items: list[ImageItem]
    images: ZipFile
    pixels: ZipFile
    image_cache: Path
    vegetation_ids: frozenset[int]
    instances: dict[str, list[Instance]]
    inputs: dict[str, str]

    def masks(self, item: ImageItem) -> Masks:
        with self.pixels.open(item.pixel_member) as stream, Image.open(stream) as png:
            if png.mode not in {"P", "L"}:
                raise ValueError(f"Expected an indexed PNG for COCO image {item.source_id}")
            return label_masks(np.asarray(png, dtype=np.uint8), self.vegetation_ids)

    def image(self, item: ImageItem) -> Path:
        path = self.image_cache / Path(item.image_member).name
        member = self.images.getinfo(item.image_member)
        if path.is_file() and zlib.crc32(path.read_bytes()) == member.CRC:
            return path
        with self.images.open(member) as source, atomic_file(path) as output:
            shutil.copyfileobj(source, output)
        return path


def _image_items(images: ZipFile, pixels: ZipFile) -> list[ImageItem]:
    masks = {
        Path(name).stem: name
        for name in pixels.namelist()
        if name.startswith("val2017/") and name.endswith(".png")
    }
    items = [
        ImageItem(str(int(Path(name).stem)), name, masks[Path(name).stem])
        for name in sorted(images.namelist())
        if name.startswith("val2017/") and name.endswith(".jpg")
    ]
    if len({item.source_id for item in items}) != 5000 or len(items) != len(masks):
        raise ValueError("Expected 5,000 matching COCO val2017 JPEGs and pixel maps")
    return items


def _read_instances(path: Path, root: Path) -> tuple[dict[str, list[Instance]], dict[str, str]]:
    with ZipFile(path) as archive:
        encoded = archive.read(INSTANCE_MEMBER)
    data = json.loads(encoded)
    category = next(entry["id"] for entry in data["categories"] if entry["name"] == "potted plant")
    return potted_instances(data["annotations"], category), {
        f"{relative_path(path, root)}!/{INSTANCE_MEMBER}": hashlib.sha256(encoded).hexdigest()
    }


@contextmanager
def dataset(context: RunContext, *, proposals: bool = False) -> Iterator[Dataset]:
    root = context.data_root
    cache = context.cache_dir / "cocostuff"
    label_path = verified_download(LABEL_FILE, root / "cocostuff/metadata/labels.txt")
    ids = parse_labels(label_path.read_text())
    if len(ids) != len(VEGETATION):
        raise ValueError("The COCO-Stuff label file lacks a requested vegetation class")
    sources = (
        (PIXEL_ARCHIVE, IMAGE_ARCHIVE, INSTANCE_ARCHIVE)
        if proposals
        else (PIXEL_ARCHIVE, IMAGE_ARCHIVE)
    )
    paths = {
        source: verified_download(source, cache / "downloads" / source.name) for source in sources
    }
    inputs = {relative_path(path, root): source.sha256 for source, path in paths.items()}
    inputs[relative_path(label_path, root)] = LABEL_FILE.sha256
    instances, receipts = _read_instances(paths[INSTANCE_ARCHIVE], root) if proposals else ({}, {})
    with ExitStack() as stack:
        images = stack.enter_context(ZipFile(paths[IMAGE_ARCHIVE]))
        pixels = stack.enter_context(ZipFile(paths[PIXEL_ARCHIVE]))
        yield Dataset(
            _image_items(images, pixels),
            images,
            pixels,
            cache / IMAGE_ARCHIVE.sha256,
            ids,
            instances,
            inputs | receipts,
        )
