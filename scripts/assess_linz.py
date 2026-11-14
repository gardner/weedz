"""Measure whether LINZ aerial imagery can support the pilot's ground-photo leads.

Usage: uv run python scripts/assess_linz.py [--store data/pilot]
       [--run nelson-tasman-3e62ad801459] [--output summary.json]

Reads the public `nz-imagery` STAC catalogue (collection JSON and each collection's
simplified capture area; no rasters are downloaded) and the pilot's photo records.
For every public-coordinate incidental photo it reports which collections cover the
point, how far their capture window is from the observation date, and how many
pixels a weed clump or the photo's positional uncertainty spans at that resolution.

The catalogue is live and changes as LINZ publishes. Each listed collection records
the catalogue's multihash of its collection JSON and of its capture area, so a rerun
can tell which inputs changed since the recorded benchmark.
"""

import argparse
import json
import math
import statistics
import time
from datetime import date, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse
from zoneinfo import ZoneInfo

import httpx

from weedz.discovery.store import Store

CATALOG = "https://nz-imagery.s3.ap-southeast-2.amazonaws.com/catalog.json"
NATIONAL = "new-zealand"
NZ = ZoneInfo("Pacific/Auckland")
CLUMPS_M = {"1m": 1.0, "3m": 3.0}
YEAR = 365
# Coarser imagery (the national 10 m satellite mosaics) cannot show a single clump.
AERIAL_MAX_GSD_M = 1.0
REQUEST_PAUSE_S = 0.2

Json = dict[str, Any]


def candidate_links(catalog: Json, regions: tuple[str, ...]) -> list[Json]:
    """Collections filed under a region, naming it in their slug, or national."""
    children = [link for link in catalog["links"] if link["rel"] == "child"]
    return [link for link in children if _is_candidate(link["href"], regions)]


def _is_candidate(href: str, regions: tuple[str, ...]) -> bool:
    # Children end <region>/<slug>/<bands>/<crs>/collection.json, relative or absolute.
    filed_under, slug = urlparse(href).path.split("/")[-5:-3]
    return filed_under in (NATIONAL, *regions) or any(region in slug for region in regions)


def _local_date(stamp: str | None) -> str | None:
    if not stamp:
        return None
    moment = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
    return moment.astimezone(NZ).date().isoformat()


def _named(collection: Json, role: str) -> list[str]:
    providers = collection.get("providers", [])
    return [provider["name"] for provider in providers if role in provider.get("roles", [])]


def parse_collection(collection: Json, link: Json) -> Json:
    """Facts used by the assessment, with the digests of the metadata they came from."""
    start, end = collection["extent"]["temporal"]["interval"][0]
    href = link["href"]
    area = collection.get("assets", {}).get("capture_area", {})
    return {
        "slug": collection["linz:slug"],
        "title": collection["title"],
        "href": href,
        "category": collection.get("linz:geospatial_category"),
        "bands": "rgbnir" if "/rgbnir/" in href else "rgb",
        "gsd_m": collection.get("gsd"),
        "license": collection.get("license"),
        "licensors": _named(collection, "licensor"),
        "producers": _named(collection, "producer"),
        "capture_start": _local_date(start),
        "capture_end": _local_date(end),
        "collection_checksum": link.get("file:checksum"),
        "capture_area_checksum": area.get("file:checksum"),
    }


def _in_ring(ring: list[list[float]], x: float, y: float) -> bool:
    inside = False
    for (x1, y1), (x2, y2) in zip(ring, ring[1:] + ring[:1], strict=True):
        if (y1 > y) != (y2 > y) and x < x1 + (y - y1) * (x2 - x1) / (y2 - y1):
            inside = not inside
    return inside


def _in_polygon(rings: list[list[list[float]]], x: float, y: float) -> bool:
    return _in_ring(rings[0], x, y) and not any(_in_ring(hole, x, y) for hole in rings[1:])


def contains(geometry: Json, x: float, y: float) -> bool:
    """Ray-casting test on a GeoJSON Polygon or MultiPolygon in lon/lat."""
    if geometry["type"] == "Polygon":
        return _in_polygon(geometry["coordinates"], x, y)
    return any(_in_polygon(polygon, x, y) for polygon in geometry["coordinates"])


def covers(capture_area: Json, x: float, y: float) -> bool:
    if capture_area["type"] == "FeatureCollection":
        return any(covers(feature, x, y) for feature in capture_area["features"])
    geometry = capture_area["geometry"] if capture_area["type"] == "Feature" else capture_area
    return contains(geometry, x, y)


def gap_days(observed: date, start: str, end: str) -> int:
    """Days from the photo to the capture window: 0 inside, + after, - before."""
    first, last = date.fromisoformat(start), date.fromisoformat(end)
    if observed < first:
        return (first - observed).days
    if observed > last:
        return -(observed - last).days
    return 0


def scale(gsd_m: float, accuracy_m: float | None) -> Json:
    clump_area = math.pi * (CLUMPS_M["3m"] / 2) ** 2
    return {
        "pixels_across": {name: size / gsd_m for name, size in CLUMPS_M.items()},
        "accuracy_radius_px": None if accuracy_m is None else accuracy_m / gsd_m,
        "search_area_vs_3m_clump": (
            None if accuracy_m is None else round(math.pi * accuracy_m**2 / clump_area, 1)
        ),
    }


def _match(item: Json, observed: date, accuracy_m: float | None) -> Json:
    return {
        "slug": item["slug"],
        "gsd_m": item["gsd_m"],
        "capture_start": item["capture_start"],
        "capture_end": item["capture_end"],
        "gap_days": gap_days(observed, item["capture_start"], item["capture_end"]),
    } | scale(item["gsd_m"], accuracy_m)


def collection_key(item: Json) -> str:
    """A survey's RGB and near-infrared products share a slug, so add the bands."""
    return f"{item['slug']}:{item['bands']}"


def _aerial(item: Json) -> bool:
    return item["gsd_m"] is not None and item["gsd_m"] <= AERIAL_MAX_GSD_M


def align(photo: Json, covering: list[Json]) -> Json:
    """An undated photo keeps its coverage, but its timing is unknown."""
    accuracy = photo.get("positional_accuracy_m")
    matches = []
    if photo.get("observed_on"):
        observed = date.fromisoformat(photo["observed_on"])
        # STAC permits open-ended intervals; a half-known window has unknown timing.
        dated = [
            item
            for item in covering
            if _aerial(item) and item["capture_start"] and item["capture_end"]
        ]
        matches = [_match(item, observed, accuracy) for item in dated]
    near = [match for match in matches if abs(match["gap_days"]) <= YEAR]
    closest = min(matches, key=lambda m: (abs(m["gap_days"]), m["gsd_m"]), default=None)
    finest = min(near, key=lambda m: (m["gsd_m"], abs(m["gap_days"])), default=None)
    return {
        "id": photo["id"],
        "region": photo["region"],
        "observed_on": photo.get("observed_on"),
        "positional_accuracy_m": accuracy,
        "covering": len(covering),
        "covering_collections": [collection_key(item) for item in covering],
        "closest": closest,
        "finest_within_year": finest,
    }


def _spread(values: list[float]) -> Json:
    if not values:
        return {"min": None, "median": None, "max": None}
    return {"min": min(values), "median": statistics.median(values), "max": max(values)}


def summarise(aligned: list[Json]) -> Json:
    accuracies = [
        a["positional_accuracy_m"] for a in aligned if a["positional_accuracy_m"] is not None
    ]
    gaps = [abs(a["closest"]["gap_days"]) for a in aligned if a["closest"]]
    return {
        "photos": len(aligned),
        "undated": sum(not a["observed_on"] for a in aligned),
        "covered": sum(a["covering"] > 0 for a in aligned),
        "captured_inside_window": sum(
            a["closest"] is not None and a["closest"]["gap_days"] == 0 for a in aligned
        ),
        "within_year": sum(a["finest_within_year"] is not None for a in aligned),
        "accuracy_unknown": len(aligned) - len(accuracies),
        "accuracy_over_20m": sum(accuracy > 20 for accuracy in accuracies),
        "accuracy_m": _spread(accuracies),
        "closest_gap_days": _spread(gaps),
    }


def assessed_photos(photos: list[Json]) -> list[Json]:
    return [
        photo
        for photo in photos
        if photo["cohort"] == "incidental" and photo["coordinate_status"] == "public"
    ]


def _fetch(client: httpx.Client, url: str) -> Json:
    time.sleep(REQUEST_PAUSE_S)  # A courtesy to the public bucket.
    response = client.get(url)
    response.raise_for_status()
    return response.json()


def _collections(client: httpx.Client, catalog_url: str) -> list[tuple[Json, Json]]:
    found = []
    for link in candidate_links(_fetch(client, catalog_url), ("nelson", "tasman")):
        url = urljoin(catalog_url, link["href"])
        raw = _fetch(client, url)
        area = _fetch(client, urljoin(url, raw["assets"]["capture_area"]["href"]))
        found.append((parse_collection(raw, link), area))
    return found


def assess(photos: list[Json], collections: list[tuple[Json, Json]]) -> Json:
    aligned, used = [], set()
    for photo in photos:
        lon, lat = photo["longitude"], photo["latitude"]
        covering = [item for item, area in collections if covers(area, lon, lat)]
        used.update(collection_key(item) for item in covering)
        aligned.append(align(photo, covering))
    listed = [item for item, _ in collections if collection_key(item) in used]
    return {"summary": summarise(aligned), "collections": listed, "photos": aligned}


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Assess LINZ imagery for pilot leads")
    parser.add_argument("--store", type=Path, default=Path("data/pilot"))
    parser.add_argument("--run", default="nelson-tasman-3e62ad801459")
    parser.add_argument("--catalog", default=CATALOG)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    # Store() would create an empty database; the pilot store is local and gitignored.
    if not (args.store / "discovery.sqlite3").exists():
        parser.error(f"no pilot store at {args.store}; see docs/local-development.md")
    photos = assessed_photos(Store(args.store).photos(args.run))
    if not photos:
        parser.error(f"run {args.run} has no public-coordinate incidental photos")
    with httpx.Client(timeout=60, headers={"User-Agent": "weedz-assessment"}) as client:
        collections = _collections(client, args.catalog)
    report = {
        "schema": 1,
        "issue": "https://github.com/gardner/weedz/issues/34",
        "command": "uv run python scripts/assess_linz.py",
        "assessed": date.today().isoformat(),
        "catalog": args.catalog,
        "run": args.run,
        "candidates": len(collections),
        "aerial_max_gsd_m": AERIAL_MAX_GSD_M,
    }
    text = json.dumps(report | assess(photos, collections), indent=2, ensure_ascii=False)
    if args.output:
        args.output.write_text(text + "\n")
    else:
        print(text)


if __name__ == "__main__":
    main()
