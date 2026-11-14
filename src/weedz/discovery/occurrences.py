"""A declared, dated snapshot of existing weed records, and distance-only comparisons.

The snapshot answers "what did we already know, from where, and as of when?". A
comparison reports distances and dates to known records; it never claims a new
locality, and a missing record is not an absence.
"""

import hashlib
import json
import math
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import httpx

from weedz.discovery.records import SPECIES

DATASET = {
    "key": "d986e335-a2e3-44f0-9606-845e2eb6081d",
    "title": "New Zealand Department of Conservation Weeds Observation Data 1983 - 2023",
    "license": "CC BY 4.0",
    "url": "https://www.gbif.org/dataset/d986e335-a2e3-44f0-9606-845e2eb6081d",
}
# GBIF backbone keys; each matched its watchlist name exactly.
TAXON_KEYS = {
    "Clematis vitalba": 3033558,
    "Cortaderia selloana": 2704523,
    "Ulex europaeus": 2951984,
}
# Declared search area covering Nelson City and Tasman District (it also clips neighbours).
BOUNDS = {"decimalLatitude": "-42.4,-40.4", "decimalLongitude": "171.9,174.0"}
RADIUS_M = 5_000.0
PAGE = 300
LIMITATIONS = [
    "Records from one declared dataset as of the retrieval date; not a complete inventory",
    "A missing record is not evidence of absence",
    "Distances are between reported points; neither point locates a plant boundary",
]
SEARCH = "https://api.gbif.org/v1/occurrence/search"
NOT_QUERIED = "Not queried in this reference snapshot"


def record_from_gbif(raw: dict[str, Any], species: str) -> dict[str, Any] | None:
    if raw.get("decimalLatitude") is None or raw.get("decimalLongitude") is None:
        return None
    return {
        "gbif_key": raw["key"],
        "species": species,
        "event_date": raw.get("eventDate"),
        "year": raw.get("year"),
        "latitude": raw["decimalLatitude"],
        "longitude": raw["decimalLongitude"],
        "uncertainty_m": raw.get("coordinateUncertaintyInMeters"),
        "status": raw.get("occurrenceStatus"),
    }


def _fetch_species(client: httpx.Client, species: str, pause: float) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    offset = 0
    while True:
        params = {
            "datasetKey": DATASET["key"],
            "taxonKey": TAXON_KEYS[species],
            "limit": PAGE,
            "offset": offset,
        } | BOUNDS
        response = client.get(SEARCH, params=params)
        response.raise_for_status()
        page = response.json()
        records += [
            record
            for raw in page["results"]
            if (record := record_from_gbif(raw, species)) is not None
        ]
        if page.get("endOfRecords", True) or not page["results"]:
            return records
        offset += PAGE
        time.sleep(pause)


def fetch_snapshot(root: Path, client: httpx.Client, at: datetime, pause: float = 1.0) -> Path:
    """Write a new, never-overwritten snapshot of the declared reference dataset."""
    destination = root / "references" / f"doc-weeds-{at.strftime('%Y%m%dT%H%M%SZ')}.json"
    if destination.exists():
        raise FileExistsError(destination)
    records = {species: _fetch_species(client, species, pause) for species in TAXON_KEYS}
    snapshot = {
        "schema": 1,
        "dataset": DATASET,
        "retrieved_at": at.isoformat(),
        "query": {"source": SEARCH, **BOUNDS},
        "taxon_keys": TAXON_KEYS,
        "counts": {species: len(rows) for species, rows in records.items()},
        "limitations": LIMITATIONS,
        "records": [row for rows in records.values() for row in rows],
    }
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(".tmp")
    temporary.write_text(json.dumps(snapshot, indent=2))
    temporary.replace(destination)
    return destination


def _latest_path(root: Path) -> Path | None:
    paths = sorted((root / "references").glob("doc-weeds-*.json"))
    return paths[-1] if paths else None


def latest_snapshot(root: Path) -> dict[str, Any] | None:
    path = _latest_path(root)
    return json.loads(path.read_text()) if path else None


def _distance_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * 6_371_000 * math.asin(math.sqrt(h))


def _not_comparable(photo: dict[str, Any]) -> str | None:
    if photo.get("coordinate_status") != "public" or photo.get("latitude") is None:
        return "Photo location is obscured or missing"
    accuracy = photo.get("positional_accuracy_m")
    if accuracy is None:
        return "Photo location accuracy is unknown"
    if accuracy > RADIUS_M:
        return f"Photo location accuracy ({accuracy:g} m) exceeds the {RADIUS_M:g} m radius"
    return None


def _compare_species(photo: dict[str, Any], records: list[dict[str, Any]]) -> dict[str, Any]:
    present = [row for row in records if row["status"] != "ABSENT"]
    distances = sorted(
        (
            (
                _distance_m(
                    photo["latitude"], photo["longitude"], row["latitude"], row["longitude"]
                ),
                row,
            )
            for row in present
        ),
        key=lambda pair: pair[0],
    )
    nearby = [row for distance, row in distances if distance <= RADIUS_M]
    years = [row["year"] for row in nearby if row["year"] is not None]
    nearest = None
    if distances:
        distance, row = distances[0]
        nearest = {
            "gbif_key": row["gbif_key"],
            "distance_m": round(distance),
            "year": row["year"],
            "uncertainty_m": row["uncertainty_m"],
        }
    return {
        "comparable": True,
        "photo_accuracy_m": photo["positional_accuracy_m"],
        "nearest": nearest,
        "radius_m": RADIUS_M,
        "within_radius": len(nearby),
        "earliest_year": min(years, default=None),
        "latest_year": max(years, default=None),
    }


def _compare_one(
    photo: dict[str, Any], records: list[dict[str, Any]], species: str, reason: str | None
) -> dict[str, Any]:
    if reason:
        return {"comparable": False, "reason": reason}
    return _compare_species(photo, [row for row in records if row["species"] == species])


def compare(
    photo: dict[str, Any], records: list[dict[str, Any]], queried: dict[str, int]
) -> dict[str, dict[str, Any]]:
    """Per watchlist species: distance and dates of known records near this photo.

    Only species the snapshot queried are compared; for the rest, a missing record
    would say nothing, so they are marked not comparable.
    """
    photo_reason = _not_comparable(photo)
    return {
        species: _compare_one(
            photo, records, species, photo_reason if species in queried else NOT_QUERIED
        )
        for species in SPECIES
    }


def with_references(root: Path, photos: list[dict[str, Any]]) -> tuple[dict | None, list[dict]]:
    """The latest snapshot's metadata, and photos annotated with their comparison."""
    path = _latest_path(root)
    if path is None:
        return None, photos
    content = path.read_bytes()
    snapshot = json.loads(content)
    records, queried = snapshot["records"], snapshot["taxon_keys"]
    metadata = {key: value for key, value in snapshot.items() if key != "records"} | {
        "snapshot_file": path.name,
        "snapshot_sha256": hashlib.sha256(content).hexdigest(),
    }
    return metadata, [
        photo | {"reference_comparison": compare(photo, records, queried)} for photo in photos
    ]
