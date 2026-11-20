"""Bounded, cached iNaturalist observations acquisition; no photo downloads."""

from collections import Counter
from pathlib import Path
from typing import Any

from shapely.geometry import shape

from pipeline.analysis import RouteArea, admit, route_area
from pipeline.cache import Acquisition, write_json

ENDPOINT = "https://api.inaturalist.org/v1/observations"


def _exclusion(
    record: dict[str, Any], area: RouteArea, first_year: int, last_year: int
) -> str | None:
    reason = admit(record, first_year, last_year)
    if reason:
        return reason
    return None if area.covers_location(record["location"]) else "outside_route_buffer"


def acquire_walk(
    client: Acquisition,
    walk: dict[str, Any],
    folder: Path,
    first_year: int,
    last_year: int,
    radius: float,
) -> dict[str, Any]:
    area = route_area(shape(walk["geometry"]), radius)
    west, south, east, north = area.bounds()
    params = {
        "taxon_id": 47170,
        "verifiable": "true",
        "photos": "true",
        "geo": "true",
        "d1": f"{first_year}-01-01",
        "d2": f"{last_year}-12-31",
        "swlat": south,
        "swlng": west,
        "nelat": north,
        "nelng": east,
        "per_page": 200,
        "order_by": "id",
        "order": "asc",
    }
    records: dict[int, dict[str, Any]] = {}
    exclusions: Counter[str] = Counter()
    cursor = 0
    pages = 0
    while True:
        page = client.json(ENDPOINT, params | {"id_above": cursor})
        results = page["results"]
        pages += 1
        if not results:
            break
        identifiers = [r["id"] for r in results]
        if identifiers != sorted(set(identifiers)) or identifiers[0] <= cursor:
            raise ValueError("iNaturalist did not honour stable ascending ID pagination")
        for record in results:
            reason = _exclusion(record, area, first_year, last_year)
            if reason:
                exclusions[reason] += 1
            else:
                records[record["id"]] = record
        cursor = identifiers[-1]
        print(f"{walk['name']}: page {pages}, {len(records)} eligible", flush=True)
        if len(results) < 200:
            break
        if pages > 500:
            raise ValueError("Acquisition exceeded bounded 100,000-row search; narrow the query")
    result = {
        "walk": walk,
        "query": params,
        "query_pages": pages,
        "exclusions": dict(exclusions),
        "records": list(records.values()),
    }
    write_json(folder / (walk["id"] + ".json"), result)
    return result
