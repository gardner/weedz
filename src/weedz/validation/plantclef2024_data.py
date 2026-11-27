"""Pinned PlantCLEF metadata, subject labels, and resumable individual photo downloads."""

import csv
import fcntl
import hashlib
import json
import logging
import time
from concurrent.futures import ThreadPoolExecutor
from contextlib import nullcontext
from dataclasses import dataclass
from itertools import batched
from pathlib import Path
from typing import Literal

import httpx
from PIL import Image
from pydantic import BaseModel

from weedz.discovery.inference import file_sha256
from weedz.validation.cocostuff_data import Download, atomic_file, verified_download
from weedz.validation.inat2021_data import Item, subject_stratum
from weedz.validation.inat2021_overlap import TRAINING_SHA256, TRAINING_URL
from weedz.validation.splits import split_of

LABELS_PATH = Path("plantclef2024/metadata/plantclef2024-training.csv")
LABELS_SHA256 = TRAINING_SHA256
IMAGE_BASE = (
    "https://lab.plantnet.org/LifeCLEF/PlantCLEF2024/single_plant_training_data/"
    "PlantCLEF2024singleplanttrainingdata"
)
SAMPLE_SALT = "weedz-plantclef2024-other-plants-v1"
OTHER_BUDGET = 5000
DOWNLOAD_WORKERS = 3
DOWNLOAD_DELAY = 0.5
PublisherSplit = Literal["val", "test"]
logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Photo:
    item: Item
    publisher_split: PublisherSplit
    organ: str
    url: str
    licence: str
    author: str
    observation_id: str


def labels_file(data_root: Path) -> Path:
    return verified_download(Download(TRAINING_URL, LABELS_SHA256), data_root / LABELS_PATH)


def _photo(row: dict[str, str], tag: PublisherSplit) -> Photo:
    name = row["image_name"]
    if Path(name).name != name or not name.endswith(".jpg") or "\\" in name:
        raise ValueError(f"Invalid PlantCLEF image name: {name}")
    species_id = row["species_id"]
    expected_url = f"{IMAGE_BASE}/{tag}/{species_id}/{name}"
    if not species_id.isdecimal() or row["image_backup_url"] != expected_url:
        raise ValueError(f"Unexpected PlantCLEF backup URL for {name}")
    taxon = " ".join(row["species"].split()[:2])
    if not row["family"] or row["genus"] != taxon.split()[0]:
        raise ValueError(f"Incomplete PlantCLEF taxonomy for {name}")
    item = Item(name, f"images/{tag}/{name}", taxon, row["genus"], row["family"], split_of(name))
    return Photo(
        item, tag, row["organ"], expected_url, row["license"], row["author"], row["obs_id"]
    )


def load_photos(path: Path) -> list[Photo]:
    """Keep labelled val/test subjects; never turn an unlabelled row into a negative."""
    photos: list[Photo] = []
    seen: set[str] = set()
    with path.open(encoding="utf-8", newline="") as stream:
        for row in csv.DictReader(stream, delimiter=";"):
            tag = row["learn_tag"]
            if tag not in {"train", "val", "test"}:
                raise ValueError(f"Unknown PlantCLEF learn_tag: {tag}")
            if tag == "train" or len(row["species"].split()) < 2:
                continue
            photo = _photo(row, "val" if tag == "val" else "test")
            if photo.item.source_id in seen:
                raise ValueError(f"Duplicate PlantCLEF image label: {photo.item.source_id}")
            seen.add(photo.item.source_id)
            photos.append(photo)
    return photos


def select_photos(
    photos: list[Photo], *, targets: bool, other_budget: int = OTHER_BUDGET
) -> list[Photo]:
    groups: dict[str, list[Photo]] = {}
    for photo in photos:
        groups.setdefault(subject_stratum(photo.item), []).append(photo)
    if targets:
        selected = groups.get("target", []) + groups.get("lookalike", [])
    else:
        others = sorted(
            groups.get("other_plants", []),
            key=lambda p: hashlib.sha256(f"{SAMPLE_SALT}:{p.item.source_id}".encode()).digest(),
        )[:other_budget]
        selected = others + [
            photo
            for group in ("lookalike", "same_genus", "same_family")
            for photo in groups.get(group, [])
        ]
    return sorted(selected, key=lambda p: p.item.source_id)


class ImageReceipt(BaseModel):
    url: str
    sha256: str
    licence: str
    author: str


def _transfer(client: httpx.Client, url: str, partial: Path) -> None:
    offset = partial.stat().st_size if partial.exists() else 0
    headers = {"Accept-Encoding": "identity"}
    if offset:
        headers["Range"] = f"bytes={offset}-"
    with client.stream("GET", url, headers=headers) as response:
        if response.status_code == 416:
            partial.unlink(missing_ok=True)
        response.raise_for_status()
        if response.status_code == 206 and not response.headers.get("Content-Range", "").startswith(
            f"bytes {offset}-"
        ):
            raise ValueError(f"Unexpected PlantCLEF download range: {url}")
        with partial.open("ab" if response.status_code == 206 else "wb") as stream:
            for chunk in response.iter_bytes():
                stream.write(chunk)


def _download(client: httpx.Client, url: str, partial: Path, delay: float) -> None:
    for attempt in range(4):
        time.sleep(delay * 2**attempt)
        try:
            _transfer(client, url, partial)
            with Image.open(partial) as image:
                image.verify()
            return
        except httpx.HTTPError:
            if attempt == 3:
                raise
        except OSError:
            # Pillow rejected truncated or non-image bytes: resuming would keep them.
            partial.unlink(missing_ok=True)
            if attempt == 3:
                raise


def _image(cache: Path, photo: Photo, client: httpx.Client, delay: float) -> str:
    path = cache / photo.item.file_name
    path.parent.mkdir(parents=True, exist_ok=True)
    receipt_path = path.with_suffix(".jpg.json")
    with path.with_suffix(".jpg.lock").open("ab") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        receipt = (
            ImageReceipt.model_validate_json(receipt_path.read_bytes())
            if receipt_path.exists()
            else None
        )
        if receipt is not None and receipt.url != photo.url:
            raise ValueError(f"PlantCLEF image receipt URL changed: {photo.item.source_id}")
        if receipt is not None and path.is_file() and file_sha256(path) == receipt.sha256:
            return receipt.sha256
        partial = path.with_suffix(".jpg.part")
        _download(client, photo.url, partial, delay)
        digest = file_sha256(partial)
        if receipt is not None and digest != receipt.sha256:
            raise ValueError(f"PlantCLEF image SHA-256 changed at source: {photo.item.source_id}")
        partial.replace(path)
        receipt = ImageReceipt(
            url=photo.url, sha256=digest, licence=photo.licence, author=photo.author
        )
        with atomic_file(receipt_path) as stream:
            stream.write(receipt.model_dump_json().encode())
        return digest


def prepare_images(
    cache: Path,
    photos: list[Photo],
    *,
    client: httpx.Client | None = None,
    delay: float = DOWNLOAD_DELAY,
) -> str:
    """Verify every scored image; keep per-image byte receipts and return their joint digest.

    The publisher supplies no image checksums. The first successful HTTPS download fixes
    each checksum locally; subsequent runs verify it. This cannot authenticate a first
    download against a publisher digest, and the result states that limit.
    """
    digests: dict[str, str] = {}
    connection = (
        nullcontext(client)
        if client is not None
        else httpx.Client(
            timeout=60, follow_redirects=True, limits=httpx.Limits(max_connections=DOWNLOAD_WORKERS)
        )
    )
    with connection as session, ThreadPoolExecutor(max_workers=DOWNLOAD_WORKERS) as pool:
        # Bounded batches preserve receipts on failure without queuing the entire dataset.
        for batch in batched(photos, 100):
            results = pool.map(lambda p: _image(cache, p, session, delay), batch)
            digests.update(
                (p.item.source_id, digest) for p, digest in zip(batch, results, strict=True)
            )
            logger.info("PlantCLEF images verified %d/%d", len(digests), len(photos))
    return hashlib.sha256(json.dumps(digests, sort_keys=True).encode()).hexdigest()
