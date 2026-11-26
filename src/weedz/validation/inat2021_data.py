"""Pinned iNat2021 validation assets and photographed-subject labels."""

import fcntl
import hashlib
import logging
import shutil
import subprocess
import tarfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from tempfile import TemporaryDirectory
from typing import Literal

from pydantic import BaseModel

from weedz.discovery.inference import file_sha256
from weedz.discovery.lookalikes import LOOKALIKES
from weedz.discovery.records import SPECIES
from weedz.validation.splits import Split, split_of

SOURCE = "https://ml-inat-competition-datasets.s3.amazonaws.com/2021"
LABELS_PATH = Path("inat2021/metadata/val.json")
LABELS_SHA256 = "a2eaf1f38e7a275432c3d6d119ed41332412484bea26d71139837c13dbf027a9"
LABELS_ARCHIVE_MD5 = "4d761e0f6a86cc63e8f7afc91f6a8f0b"
IMAGES_ARCHIVE_MD5 = "f6f6e0e242e3d4c9569ba56400938afc"

TARGETS = tuple(SPECIES)
LOOKALIKE_NAMES = frozenset(row["name"] for row in LOOKALIKES.values())
TARGET_FAMILIES = frozenset({"Ranunculaceae", "Poaceae", "Fabaceae"})
TARGET_GENERA = frozenset(name.split()[0] for name in TARGETS)
Stratum = Literal["target", "lookalike", "same_genus", "same_family", "other_plants"]
NEGATIVE_STRATA: tuple[Stratum, ...] = ("lookalike", "same_genus", "same_family", "other_plants")

logger = logging.getLogger(__name__)


class Category(BaseModel):
    id: int
    name: str
    genus: str
    family: str
    supercategory: str


class SourceImage(BaseModel):
    id: int
    file_name: str


class Annotation(BaseModel):
    image_id: int
    category_id: int


class Labels(BaseModel):
    categories: list[Category]
    images: list[SourceImage]
    annotations: list[Annotation]


@dataclass(frozen=True)
class Item:
    source_id: str
    file_name: str
    taxon: str
    genus: str
    family: str
    split: Split


def subject_stratum(item: Item) -> Stratum:
    if item.taxon in TARGETS:
        return "target"
    if item.taxon in LOOKALIKE_NAMES or item.genus in LOOKALIKE_NAMES:
        return "lookalike"
    if item.genus in TARGET_GENERA:
        return "same_genus"
    if item.family in TARGET_FAMILIES:
        return "same_family"
    return "other_plants"


def _plant_item(annotation: Annotation, category: Category, image: SourceImage) -> Item:
    path = PurePosixPath(image.file_name)
    if len(path.parts) != 3 or path.parts[0] != "val" or ".." in path.parts:
        raise ValueError(f"Invalid iNat2021 validation image path: {path}")
    source_id = str(annotation.image_id)
    return Item(
        source_id, str(path), category.name, category.genus, category.family, split_of(source_id)
    )


def load_items(path: Path) -> list[Item]:
    labels = Labels.model_validate_json(path.read_bytes())
    categories = {category.id: category for category in labels.categories}
    images = {image.id: image for image in labels.images}
    if len(categories) != len(labels.categories) or len(images) != len(labels.images):
        raise ValueError("Duplicate iNat2021 category or image ID")
    seen: set[int] = set()
    items: list[Item] = []
    for annotation in labels.annotations:
        if annotation.image_id in seen:
            raise ValueError(f"Image {annotation.image_id} has multiple subject labels")
        seen.add(annotation.image_id)
        category = categories[annotation.category_id]
        image = images[annotation.image_id]
        if category.supercategory == "Plants":
            items.append(_plant_item(annotation, category, image))
    return items


def _verify(path: Path, md5: str) -> None:
    with path.open("rb") as stream:
        digest = hashlib.file_digest(stream, lambda: hashlib.md5(usedforsecurity=False))
    if digest.hexdigest() != md5:
        raise ValueError(f"Publisher checksum mismatch for {path}")


def _archive(cache: Path, filename: str, md5: str) -> Path:
    cache.mkdir(parents=True, exist_ok=True)
    path = cache / filename
    partial = path.with_suffix(".gz.part")
    with path.with_suffix(".lock").open("ab") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if not path.exists():
            logger.info("Downloading %s to %s", filename, cache)
            subprocess.run(
                [
                    "curl",
                    "--fail",
                    "--location",
                    "--retry",
                    "4",
                    "--continue-at",
                    "-",
                    "--output",
                    str(partial),
                    f"{SOURCE}/{filename}",
                ],
                check=True,
            )
            _verify(partial, md5)
            partial.replace(path)
        else:
            _verify(path, md5)
    return path


def _extract_member(source: tarfile.TarFile, member: tarfile.TarInfo, dest: Path) -> None:
    if not member.isfile():
        raise ValueError(f"Expected a regular iNat2021 file: {member.name}")
    stream = source.extractfile(member)
    if stream is None:
        raise ValueError(f"Missing iNat2021 archive member: {member.name}")
    dest.parent.mkdir(parents=True, exist_ok=True)
    with stream, TemporaryDirectory(dir=dest.parent) as scratch:
        temporary = Path(scratch) / "file"
        with temporary.open("wb") as output:
            shutil.copyfileobj(stream, output)
        temporary.replace(dest)


def labels_file(data_root: Path, cache: Path) -> Path:
    path = data_root / LABELS_PATH
    if not path.exists():
        archive = _archive(cache, "val.json.tar.gz", LABELS_ARCHIVE_MD5)
        with tarfile.open(archive) as source:
            _extract_member(source, source.getmember("val.json"), path)
    if file_sha256(path) != LABELS_SHA256:
        raise ValueError("iNat2021 val.json SHA-256 mismatch")
    return path


def prepare_images(data_root: Path, cache: Path, items: list[Item]) -> None:
    """Extract only requested images, publishing each file atomically."""
    root = data_root / "inat2021"
    cache.mkdir(parents=True, exist_ok=True)
    with (cache / "extract.lock").open("ab") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        missing = {item.file_name for item in items if not (root / item.file_name).is_file()}
        if not missing:
            return
        archive = _archive(cache, "val.tar.gz", IMAGES_ARCHIVE_MD5)
        logger.info("Extracting %d iNat2021 images", len(missing))
        with tarfile.open(archive, "r|gz") as source:
            for member in source:
                name = member.name.removeprefix("./")
                if name in missing:
                    _extract_member(source, member, root / name)
                    missing.remove(name)
                if not missing:
                    return
        raise ValueError(f"Verified archive is missing {len(missing)} requested images")
