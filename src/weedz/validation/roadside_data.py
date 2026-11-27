"""Publisher-positive labels, frozen membership, spatial strata and pinned downloads."""

import csv
import hashlib
import json
import logging
import math
import re
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import TypedDict
from urllib.parse import unquote
from urllib.request import Request, urlopen

from scipy.spatial import KDTree

from weedz.validation.splits import Split, split_of

DATASET = "danish-roadside"
GROUPS = (
    "Solidago",
    "Cytisus scoparius",
    "Rosa rugosa",
    "Lupinus polyphyllus",
    "Pastinaca sativa",
    "Reynoutria",
)
FOLDERS = (
    "1_solidago",
    "2_cytisus_scoparius",
    "3_rosa_rugosa",
    "4_lupinus_polyphyllus",
    "5_pastinaca_sativa",
    "6_reynoutria",
    "7_no_species",
)
SPECIES = (
    ("Solidago canadensis L.", "Solidago gigantea Aiton"),
    ("Cytisus scoparius (L.) Link",),
    ("Rosa rugosa Thunb.",),
    ("Lupinus polyphyllus Lindl.",),
    ("Pastinaca sativa L.",),
    ("Reynoutria japonica Houtt.", "Reynoutria sachalinensis (F.Schmidt) Nakai"),
)
PINS_PATH = Path(__file__).with_name("roadside_pins.json")
PINS_SHA256 = "1ebf35595af17af9651d88892355e2b6904706194f4b250b91bf87b71051ccad"
DISTANCE_METRES = 100
Membership = tuple[str, str, str]
logger = logging.getLogger(__name__)


class Pin(TypedDict):
    url: str
    sha256: str


@dataclass(frozen=True)
class Item:
    source_id: str
    file_name: str
    source_split: str
    positives: tuple[str, ...]
    split: Split
    distance_filtered: bool


def sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def fetch_verified(path: Path, url: str, expected: str, staging: Path | None = None) -> None:
    """Resume partial downloads, then verify before making them available to inference."""
    if path.exists():
        if sha256(path) != expected:
            raise ValueError(f"Roadside checksum mismatch: {path.name}")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    partial = (staging or path.parent) / (expected + ".part")
    partial.parent.mkdir(parents=True, exist_ok=True)
    if partial.exists() and sha256(partial) == expected:
        _publish_download(partial, path)
        return
    _stream_download(partial, url)
    if sha256(partial) != expected:
        partial.unlink()
        raise ValueError(f"Roadside download checksum mismatch: {path.name}")
    _publish_download(partial, path)


def _stream_download(partial: Path, url: str) -> None:
    offset = partial.stat().st_size if partial.exists() else 0
    request = Request(url, headers={"Range": f"bytes={offset}-"} if offset else {})
    with urlopen(request, timeout=120) as response:
        resume = offset and response.status == 206
        if resume and not response.headers.get("Content-Range", "").startswith(f"bytes {offset}-"):
            raise ValueError("Invalid resumed roadside download range")
        with partial.open("ab" if resume else "wb") as stream:
            while chunk := response.read(1024 * 1024):
                stream.write(chunk)


def _publish_download(partial: Path, path: Path) -> None:
    # Keep the verified staging file until an atomic rename publishes the copy.
    temporary = path.with_name(path.name + ".tmp")
    shutil.copyfile(partial, temporary)
    temporary.replace(path)
    partial.unlink()


def source_pins() -> dict[str, Pin]:
    if sha256(PINS_PATH) != PINS_SHA256:
        raise ValueError("Roadside source manifest checksum mismatch")
    return json.loads(PINS_PATH.read_text())


def prepare_metadata(root: Path, staging: Path) -> dict[str, str]:
    pins = source_pins()
    inputs = {}
    manifest = root / DATASET / "metadata/source-pins.json"
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_bytes(PINS_PATH.read_bytes())
    inputs[f"{DATASET}/metadata/source-pins.json"] = sha256(manifest)
    for relative, pin in pins.items():
        if relative.startswith("metadata/"):
            path = root / DATASET / relative
            fetch_verified(path, pin["url"], pin["sha256"], staging)
            inputs[f"{DATASET}/{relative}"] = pin["sha256"]
    return inputs


def index_names(html: str) -> list[str]:
    names = [
        unquote(name).removesuffix(".pth")
        for name in re.findall(r'href="([^"/]+\.jpg\.pth)"', html)
    ]
    if len(set(names)) != len(names):
        raise ValueError("Duplicate roadside index filename")
    for name in names:
        position(name)
    return sorted(names)


def read_membership(root: Path) -> list[Membership]:
    rows = []
    for split in ("train", "val", "test", "multilabel"):
        for folder in ("dummy_class",) if split == "multilabel" else FOLDERS:
            path = root / DATASET / "metadata/indexes" / split / f"{folder}.html"
            rows.extend((split, folder, name) for name in index_names(path.read_text()))
    return rows


def position(name: str) -> tuple[float, float, float]:
    match = re.fullmatch(
        r"GT_\d{4}-\d{2}-\d{2}T[\d_.]+Z_CT_[\d.]+_(-?[\d.]+)_(-?[\d.]+)\.jpg", name
    )
    if match is None:
        raise ValueError(f"Invalid roadside filename: {name}")
    lon, lat = (math.radians(float(value)) for value in match.groups())
    radius = 6371008.8
    return (
        radius * math.cos(lat) * math.cos(lon),
        radius * math.cos(lat) * math.sin(lon),
        radius * math.sin(lat),
    )


def _multilabel(path: Path) -> dict[str, tuple[str, ...]]:
    labels = {}
    with path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream, delimiter=";")
        if reader.fieldnames != ["image_name", *GROUPS]:
            raise ValueError("Unexpected roadside multilabel columns")
        for row in reader:
            name = row["image_name"]
            position(name)
            if name in labels:
                raise ValueError("Duplicate roadside multilabel photo")
            if any(row[group] not in {"", "1"} for group in GROUPS):
                raise ValueError("Roadside labels must be positive or blank")
            labels[name] = tuple(group for group in GROUPS if row[group] == "1")
    return labels


def load_items(csv_path: Path, membership: list[Membership]) -> list[Item]:
    labels = _multilabel(csv_path)
    if set(labels) != {name for split, _, name in membership if split == "multilabel"}:
        raise ValueError("Roadside CSV and multilabel membership disagree")
    if len(set(membership)) != len(membership):
        raise ValueError("Duplicate roadside membership")
    trees = {}
    for cohort, other in (("test", "multilabel"), ("multilabel", "test")):
        points = [
            position(name) for split, _, name in membership if split in {"train", "val", other}
        ]
        trees[cohort] = KDTree(points) if points else None
    items = []
    seen: set[str] = set()
    for split, folder, name in membership:
        if split not in trees:
            continue
        if name in seen:
            raise ValueError("Duplicate roadside scoring photo")
        seen.add(name)
        positives = labels[name] if split == "multilabel" else _folder_label(folder)
        tree = trees[split]
        far = tree is None or float(tree.query(position(name))[0]) > DISTANCE_METRES
        items.append(Item(name, f"{split}/{folder}/{name}", split, positives, split_of(name), far))
    return items


def _folder_label(folder: str) -> tuple[str, ...]:
    if folder not in FOLDERS:
        raise ValueError(f"Unknown roadside source class: {folder}")
    index = FOLDERS.index(folder)
    return (GROUPS[index],) if index < len(GROUPS) else ()


def groups_for(names: tuple[str, ...]) -> set[str]:
    """Match species after the suggestion budget; two siblings recover one group pair."""
    canonical = {" ".join(name.split()[:2]) for name in names}
    return {
        group
        for group, taxa in zip(GROUPS, SPECIES, strict=True)
        if group in names or any(" ".join(taxon.split()[:2]) in canonical for taxon in taxa)
    }


def acquire_assets(
    root: Path, staging: Path, items: list[Item], *, baseline: bool
) -> tuple[list[Path], dict[str, str]]:
    from concurrent.futures import ThreadPoolExecutor

    pins = source_pins()
    kind = "features" if baseline else "images"
    relatives = [f"{kind}/{item.file_name}" + (".pth" if baseline else "") for item in items]

    def fetch(relative: str) -> Path:
        pin = pins[relative]
        path = root / DATASET / relative
        fetch_verified(path, pin["url"], pin["sha256"], staging)
        return path

    logger.info("Verifying/downloading %d roadside %s", len(relatives), kind)
    with ThreadPoolExecutor(max_workers=4) as pool:
        paths = list(pool.map(fetch, relatives))
    return paths, {f"{DATASET}/{rel}": pins[rel]["sha256"] for rel in relatives}
