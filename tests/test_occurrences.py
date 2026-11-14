"""Reference records are a declared, dated snapshot; comparisons never overstate precision."""

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
import pytest

from weedz.discovery.occurrences import (
    DATASET,
    TAXON_KEYS,
    compare,
    fetch_snapshot,
    latest_snapshot,
    record_from_gbif,
)


def gbif(key: int, lat: float | None = -41.27, lon: float | None = 173.28, **extra: Any) -> dict:
    return {
        "key": key,
        "scientificName": "Ulex europaeus L.",
        "eventDate": "2015-03-02T00:00",
        "year": 2015,
        "decimalLatitude": lat,
        "decimalLongitude": lon,
        "coordinateUncertaintyInMeters": 100.0,
        "occurrenceStatus": "PRESENT",
    } | extra


def test_records_keep_only_what_the_comparison_needs() -> None:
    record = record_from_gbif(gbif(1), "Ulex europaeus")
    assert record == {
        "gbif_key": 1,
        "species": "Ulex europaeus",
        "event_date": "2015-03-02T00:00",
        "year": 2015,
        "latitude": -41.27,
        "longitude": 173.28,
        "uncertainty_m": 100.0,
        "status": "PRESENT",
    }
    assert record_from_gbif(gbif(2, lat=None), "Ulex europaeus") is None


def transport(pages: dict[int, list[list[dict]]], seen: list[httpx.Request]) -> httpx.MockTransport:
    def handle(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        taxon = int(request.url.params["taxonKey"])
        offset = int(request.url.params["offset"])
        batches = pages.get(taxon, [[]])
        index = offset // 300
        results = batches[index] if index < len(batches) else []
        return httpx.Response(
            200, json={"results": results, "endOfRecords": index >= len(batches) - 1}
        )

    return httpx.MockTransport(handle)


def test_snapshot_pages_each_watchlist_taxon_and_records_its_as_of_date(tmp_path: Path) -> None:
    gorse = TAXON_KEYS["Ulex europaeus"]
    seen: list[httpx.Request] = []
    pages = {gorse: [[gbif(index) for index in range(300)], [gbif(300)]]}
    client = httpx.Client(transport=transport(pages, seen))
    at = datetime(2026, 11, 14, 5, 0, tzinfo=UTC)
    path = fetch_snapshot(tmp_path, client, at, pause=0)
    snapshot = json.loads(path.read_text())
    assert snapshot["dataset"] == DATASET
    assert snapshot["retrieved_at"] == at.isoformat()
    assert snapshot["taxon_keys"] == TAXON_KEYS
    assert snapshot["counts"]["Ulex europaeus"] == 301
    assert all(r.url.params["datasetKey"] == DATASET["key"] for r in seen)
    assert latest_snapshot(tmp_path) == snapshot
    with pytest.raises(FileExistsError):
        fetch_snapshot(tmp_path, client, at, pause=0)


def test_no_snapshot_means_no_comparison(tmp_path: Path) -> None:
    assert latest_snapshot(tmp_path) is None


def photo(**overrides: Any) -> dict:
    return {
        "coordinate_status": "public",
        "latitude": -41.2637,
        "longitude": 173.2880,
        "positional_accuracy_m": 8.0,
    } | overrides


def record(gbif_key: int, lat: float, year: int, status: str = "PRESENT") -> dict:
    return {
        "gbif_key": gbif_key,
        "species": "Ulex europaeus",
        "event_date": f"{year}-01-01",
        "year": year,
        "latitude": lat,
        "longitude": 173.2880,
        "uncertainty_m": None,
        "status": status,
    }


def test_comparison_reports_nearest_record_and_nearby_years() -> None:
    records = [
        record(1, -41.2737, 2015),  # about 1.1 km
        record(2, -41.2937, 2003),  # about 3.3 km
        record(3, -41.4637, 1990),  # about 22 km
        record(4, -41.2647, 2020, status="ABSENT"),
    ]
    result = compare(photo(), records)
    gorse = result["Ulex europaeus"]
    assert gorse["comparable"] is True
    assert gorse["nearest"]["gbif_key"] == 1
    assert 1_000 < gorse["nearest"]["distance_m"] < 1_200
    assert gorse["nearest"]["year"] == 2015
    assert gorse["within_radius"] == 2
    assert (gorse["earliest_year"], gorse["latest_year"]) == (2003, 2015)
    assert gorse["photo_accuracy_m"] == 8.0
    assert result["Clematis vitalba"]["nearest"] is None
    assert result["Clematis vitalba"]["within_radius"] == 0


def test_unknown_or_imprecise_photo_locations_are_not_comparable() -> None:
    for location in [
        photo(coordinate_status="obscured"),
        photo(latitude=None, longitude=None, coordinate_status="missing"),
        photo(positional_accuracy_m=None),
        photo(positional_accuracy_m=6_000.0),
    ]:
        gorse = compare(location, [record(1, -41.2737, 2015)])["Ulex europaeus"]
        assert gorse["comparable"] is False
        assert gorse["reason"]


def test_records_at_the_same_distance_do_not_break_the_comparison() -> None:
    twins = [record(1, -41.2737, 2015), record(2, -41.2737, 2016)]
    assert compare(photo(), twins)["Ulex europaeus"]["within_radius"] == 2
