"""Audit the optional PlantCLEF training metadata against iNat2021 val."""

import csv
import re
from collections import Counter
from pathlib import Path

from weedz.discovery.inference import file_sha256
from weedz.validation.inat2021_data import TARGETS, Item

TRAINING_CSV = Path("inat2021/metadata/plantclef2024-training.csv")
TRAINING_URL = (
    "https://lab.plantnet.org/LifeCLEF/PlantCLEF2024/single_plant_training_data/"
    "PlantCLEF2024singleplanttrainingdata.csv"
)
TRAINING_SHA256 = "ceacfd939c2223fb1e619c043fb895f408529cb7efd285ba1408c4f23283366f"
INAT_RECORD = re.compile(
    r"(?:inaturalist\.org/(?:observations|photos)/|"
    r"inaturalist-open-data\.s3\.amazonaws\.com/photos/|static\.inaturalist\.org/photos/)\d+",
    re.IGNORECASE,
)


def audit_overlap(data_root: Path, items: list[Item]) -> tuple[dict[str, str], str]:
    path = data_root / TRAINING_CSV
    if not path.exists():
        return (
            {},
            "The optional pinned PlantCLEF training CSV was unavailable for the overlap audit.",
        )
    if file_sha256(path) != TRAINING_SHA256:
        raise ValueError(f"PlantCLEF training metadata SHA-256 mismatch: {TRAINING_CSV}")
    val_images = {Path(item.file_name).stem for item in items}
    totals: Counter[str] = Counter()
    target_sources: Counter[tuple[str, str]] = Counter()
    with path.open(encoding="utf-8", newline="") as stream:
        for row in csv.DictReader(stream, delimiter=";"):
            totals["rows"] += 1
            totals["links"] += bool(INAT_RECORD.search(f"{row['url']} {row['references']}"))
            totals["matches"] += Path(row["image_name"]).stem in val_images
            taxon = " ".join(row["species"].split()[:2])
            if taxon in TARGETS:
                target_sources[taxon, row["dataset"]] += 1
    sources = ", ".join(
        f"{taxon} ({source}, {count:,})"
        for (taxon, source), count in sorted(target_sources.items())
    )
    return {str(TRAINING_CSV): TRAINING_SHA256}, (
        f"PlantCLEF training metadata ({totals['rows']:,} rows) lists {sources}. "
        f"It contains {totals['links']:,} rows linking to iNaturalist records or photos and "
        f"{totals['matches']:,} direct filename matches to iNat2021 plant validation images. "
        "The val export uses opaque UUID filenames and has no original iNaturalist photo or "
        "observation IDs. Direct ID overlap and re-encoded duplicate images remain unverified."
    )
