"""Each photo states where a search could start and what its dates can and cannot say."""

from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient
from test_discovery import observation

from weedz.discovery.activities import export
from weedz.discovery.api import create_app
from weedz.discovery.limits import (
    CAMERA_TO_PLANT_ALLOWANCE_M,
    SITE_CONTEXT_ACCURACY_M,
    limits,
    search_area,
    search_area_summary,
)
from weedz.discovery.records import RunSpec
from weedz.discovery.source import photo_from_observation
from weedz.discovery.store import Store

SCREENED_AT = "2026-11-14T05:04:00+00:00"


def photo(**fields: Any) -> dict[str, Any]:
    return {
        "id": "p",
        "coordinate_status": "public",
        "latitude": -41.27,
        "longitude": 173.28,
        "positional_accuracy_m": 12.0,
        "observed_on": "2024-06-01",
        "uploaded_at": "2024-06-03T08:00:00Z",
        "screened_at": SCREENED_AT,
    } | fields


def test_a_public_point_with_known_accuracy_gives_a_search_area_around_the_camera() -> None:
    area = search_area(photo())
    assert area.status == "searchable"
    assert area.centre == (-41.27, 173.28)
    assert area.centre_is == "observation point (where the photographer was), not a plant point"
    assert area.accuracy_m == 12.0
    assert area.allowance_m == CAMERA_TO_PLANT_ALLOWANCE_M
    assert area.radius_m == 12.0 + CAMERA_TO_PLANT_ALLOWANCE_M
    assert area.site_context is True
    assert "bearing" in area.allowance_reason


def test_the_allowance_is_declared_not_measured() -> None:
    assert CAMERA_TO_PLANT_ALLOWANCE_M > 0
    assert SITE_CONTEXT_ACCURACY_M == 20.0
    imprecise = search_area(photo(positional_accuracy_m=1634.0))
    assert imprecise.status == "searchable"
    assert imprecise.radius_m == 1634.0 + CAMERA_TO_PLANT_ALLOWANCE_M
    assert imprecise.site_context is False


def test_obscured_missing_and_unknown_accuracy_locations_are_not_searchable() -> None:
    cases = {
        "obscured": photo(coordinate_status="obscured"),
        "missing": photo(coordinate_status="missing", latitude=None, longitude=None),
        "accuracy_unknown": photo(positional_accuracy_m=None),
    }
    for status, case in cases.items():
        area = search_area(case)
        assert area.status == status
        # No centre or radius is ever invented, not even the obscured point.
        assert (area.centre, area.radius_m, area.site_context) == (None, None, False)
        assert area.reason
    assert search_area(photo(latitude=None)).status == "missing"


def test_dates_are_distinct_with_their_gaps_and_no_presumed_presence() -> None:
    dates = limits(photo()).dates
    assert (dates.photographed, dates.uploaded, dates.screened) == (
        "2024-06-01",
        "2024-06-03",
        "2026-11-14",
    )
    assert dates.days_photo_to_upload == 2
    assert dates.days_photo_to_screening == 896
    assert "not that it is there now" in dates.current_presence
    assert "2024-06-01" in dates.current_presence
    # A candidate is not a confirmed plant, so presence is stated conditionally.
    assert dates.current_presence.startswith("If the plant is visible")


def test_a_partial_date_is_kept_as_given_without_inventing_day_gaps() -> None:
    for partial in ["2024-06", "2024", "not a date"]:
        dates = limits(photo(observed_on=partial)).dates
        assert dates.photographed == partial
        assert (dates.days_photo_to_upload, dates.days_photo_to_screening) == (None, None)
        assert partial in dates.current_presence
        assert dates.current_presence.startswith("If the plant is visible")


def test_a_photo_not_yet_screened_has_no_screening_date() -> None:
    dates = limits(photo(screened_at=None)).dates
    assert (dates.screened, dates.days_photo_to_screening) == (None, None)


def test_unknown_dates_stay_unknown() -> None:
    dates = limits(photo(observed_on=None, uploaded_at=None)).dates
    assert (dates.photographed, dates.uploaded) == (None, None)
    assert (dates.days_photo_to_upload, dates.days_photo_to_screening) == (None, None)
    assert "date unknown" in dates.current_presence.lower()
    # Nor does an undated candidate presuppose that the plant was ever there.
    assert "if the plant is visible" in dates.current_presence.lower()
    assert "not that it is there now" not in dates.current_presence


def test_search_area_summary_counts_each_status_and_site_context() -> None:
    photos = [
        photo(id="a"),
        photo(id="b", positional_accuracy_m=300.0),
        photo(id="c", coordinate_status="obscured"),
        photo(id="d", positional_accuracy_m=None),
        photo(id="d", positional_accuracy_m=None),
    ]
    assert search_area_summary(photos) == {
        "searchable": 2,
        "site_context_precision": 1,
        "obscured": 1,
        "accuracy_unknown": 1,
    }
    assert search_area_summary([]) == {"searchable": 0, "site_context_precision": 0}


def stored_run(root: Path, **fields: object) -> TestClient:
    store = Store(root)
    store.create_run("run", RunSpec())
    raw = observation() | {"obscured": False, "geoprivacy": None, "positional_accuracy": 8} | fields
    record = photo_from_observation(raw, "Nelson", "incidental")
    assert record is not None
    store.save_photos("run", [record])
    return TestClient(create_app(root))


def test_run_detail_and_export_carry_each_photos_limits(tmp_path: Path) -> None:
    client = stored_run(tmp_path)
    [unscreened] = client.get("/runs/run").json()["photos"]
    assert unscreened["limits"]["dates"]["screened"] is None
    Store(tmp_path).score("run", unscreened["id"], {"best_species": "Ulex europaeus"})
    [detailed] = client.get("/runs/run").json()["photos"]
    assert detailed["limits"]["search_area"]["status"] == "searchable"
    assert detailed["limits"]["search_area"]["radius_m"] == 8 + CAMERA_TO_PLANT_ALLOWANCE_M
    # The screening date is when this photo was scored, not when the run was queued.
    assert detailed["limits"]["dates"]["screened"] == detailed["screened_at"][:10]
    exported = export(Store(tmp_path), "run")
    assert exported["photos"][0]["limits"] == detailed["limits"]
    [stated] = [item for item in exported["limitations"] if "search area" in item.lower()]
    # Candidates are not confirmed plants, so the export never asserts presence.
    assert "if a plant is visible" in stated.lower()
    assert "shows a plant was there" not in stated.lower()
