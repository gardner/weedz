"""The LINZ aerial-imagery assessment is reproducible from STAC metadata alone."""

import importlib.util
from datetime import date
from pathlib import Path
from typing import Any

import pytest

spec = importlib.util.spec_from_file_location(
    "assess_linz", Path(__file__).parents[1] / "scripts" / "assess_linz.py"
)
assert spec and spec.loader
assess = importlib.util.module_from_spec(spec)
spec.loader.exec_module(assess)


def catalog() -> dict[str, Any]:
    hrefs = [
        "./nelson/nelson_2025_0.075m/rgb/2193/collection.json",
        "./tasman/tasman_2024-2025_0.25m/rgbnir/2193/collection.json",
        "./marlborough/marlborough_tasman_sn8415_1984_0.375m/rgb/2193/collection.json",
        "./new-zealand/new-zealand_2024-2025_10m/rgb/2193/collection.json",
        "./otago/otago_2020_0.3m/rgb/2193/collection.json",
        "./nelson/top-of-the-south-flood_2022_0.15m/rgb/2193/collection.json",
    ]
    return {
        "links": [{"rel": "root", "href": "./catalog.json"}]
        + [
            {"rel": "child", "href": href, "file:checksum": f"1220{i}"}
            for i, href in enumerate(hrefs)
        ]
    }


def collection(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "title": "Tasman 0.25m Near-Infrared Aerial Photos (2024-2025)",
        "license": "CC-BY-4.0",
        "providers": [
            {"name": "Toitū Te Whenua Land Information New Zealand", "roles": ["host"]},
            {"name": "Aerial Surveys", "roles": ["producer"]},
            {"name": "Tasman District Council", "roles": ["licensor"]},
        ],
        "linz:geospatial_category": "near-infrared-aerial-photos",
        "linz:slug": "tasman_2024-2025_0.25m",
        "gsd": 0.25,
        "extent": {"temporal": {"interval": [["2024-12-05T11:00:00Z", "2025-03-26T11:00:00Z"]]}},
    }
    return base | overrides


SQUARE = {"type": "Polygon", "coordinates": [[[0, 0], [10, 0], [10, 10], [0, 10], [0, 0]]]}
HOLE = [[4, 4], [6, 4], [6, 6], [4, 6], [4, 4]]


def test_candidates_are_the_regions_own_collections_plus_named_and_national_ones() -> None:
    links = assess.candidate_links(catalog(), ("nelson", "tasman"))
    hrefs = [link["href"] for link in links]
    assert len(hrefs) == 5
    assert not any("otago" in href for href in hrefs)
    # Filed under the region even though the slug names a place, not the region.
    assert "./nelson/top-of-the-south-flood_2022_0.15m/rgb/2193/collection.json" in hrefs


def test_collection_records_the_digests_of_the_metadata_it_was_read_from() -> None:
    raw = collection(
        assets={"capture_area": {"href": "./capture-area.geojson", "file:checksum": "1220area"}}
    )
    link = {
        "href": "./tasman/tasman_2024-2025_0.25m/rgb/2193/collection.json",
        "file:checksum": "1220collection",
    }
    parsed = assess.parse_collection(raw, link)
    assert parsed["collection_checksum"] == "1220collection"
    assert parsed["capture_area_checksum"] == "1220area"


def test_collection_keeps_scale_bands_licence_attribution_and_local_dates() -> None:
    href = "./tasman/tasman_2024-2025_0.25m/rgbnir/2193/collection.json"
    parsed = assess.parse_collection(collection(), {"href": href})
    assert parsed["slug"] == "tasman_2024-2025_0.25m"
    assert parsed["bands"] == "rgbnir"
    assert parsed["gsd_m"] == 0.25
    assert parsed["license"] == "CC-BY-4.0"
    assert parsed["licensors"] == ["Tasman District Council"]
    assert parsed["producers"] == ["Aerial Surveys"]
    # LINZ encodes season bounds as New Zealand midnights in UTC.
    assert parsed["capture_start"] == "2024-12-06"
    assert parsed["capture_end"] == "2025-03-27"


def test_collection_without_gsd_or_dates_is_kept_as_unknown() -> None:
    raw = collection(extent={"temporal": {"interval": [[None, None]]}})
    del raw["gsd"]
    parsed = assess.parse_collection(raw, {"href": "./tasman/x/rgb/2193/collection.json"})
    assert parsed["gsd_m"] is None
    assert parsed["capture_start"] is None
    assert parsed["bands"] == "rgb"


def test_point_in_polygon_respects_holes_and_multipolygons() -> None:
    assert assess.contains(SQUARE, 5, 1)
    assert not assess.contains(SQUARE, 11, 5)
    holed = {"type": "Polygon", "coordinates": [SQUARE["coordinates"][0], HOLE]}
    assert not assess.contains(holed, 5, 5)
    assert assess.contains(holed, 2, 2)
    multi = {
        "type": "MultiPolygon",
        "coordinates": [SQUARE["coordinates"], [[[20, 20], [30, 20], [30, 30], [20, 20]]]],
    }
    assert assess.contains(multi, 28, 22)


def test_capture_area_features_and_collections_are_unwrapped() -> None:
    feature = {"type": "Feature", "geometry": SQUARE}
    assert assess.covers(feature, 5, 5)
    assert assess.covers({"type": "FeatureCollection", "features": [feature]}, 5, 5)
    assert not assess.covers({"type": "FeatureCollection", "features": []}, 5, 5)


@pytest.mark.parametrize(
    ("observed", "gap"),
    [(date(2024, 12, 31), 0), (date(2024, 12, 1), 5), (date(2025, 4, 1), -5)],
)
def test_gap_is_zero_inside_the_window_and_signed_outside_it(observed: date, gap: int) -> None:
    # Positive: imagery captured after the photo. Negative: before it.
    assert assess.gap_days(observed, "2024-12-06", "2025-03-27") == gap


def test_scale_reports_pixels_across_a_clump_and_the_photo_uncertainty() -> None:
    scale = assess.scale(0.25, accuracy_m=10.0)
    assert scale["pixels_across"] == {"1m": 4.0, "3m": 12.0}
    assert scale["accuracy_radius_px"] == 40.0
    # A 10 m radius circle is about 44 times the area of a 3 m wide clump.
    assert scale["search_area_vs_3m_clump"] == pytest.approx(44.4, abs=0.1)
    assert assess.scale(0.25, accuracy_m=None)["accuracy_radius_px"] is None


def photo(**overrides: Any) -> dict[str, Any]:
    return {
        "id": "p1",
        "cohort": "incidental",
        "region": "Tasman",
        "observed_on": "2024-12-31",
        "latitude": 5.0,
        "longitude": 5.0,
        "positional_accuracy_m": 6.0,
        "coordinate_status": "public",
    } | overrides


def parsed(slug: str, gsd: float, start: str, end: str) -> dict[str, Any]:
    return {"slug": slug, "gsd_m": gsd, "capture_start": start, "capture_end": end}


def test_alignment_picks_the_closest_capture_and_the_finest_within_a_year() -> None:
    covering = [
        parsed("season", 0.25, "2024-12-06", "2025-03-27"),
        parsed("urban", 0.075, "2025-12-01", "2025-12-04"),
        parsed("old", 0.3, "2018-12-01", "2019-03-01"),
        parsed("satellite", 10.0, "2024-09-01", "2025-04-30"),
    ]
    aligned = assess.align(photo(), covering)
    assert aligned["covering"] == 4
    assert aligned["closest"]["slug"] == "season"
    assert aligned["closest"]["gap_days"] == 0
    assert aligned["finest_within_year"]["slug"] == "urban"
    assert aligned["finest_within_year"]["gap_days"] == 335
    assert aligned["finest_within_year"]["accuracy_radius_px"] == 80.0


def test_satellite_mosaics_are_never_the_aerial_match() -> None:
    # One 10 m pixel is wider than any clump, so a same-season mosaic corroborates nothing.
    aligned = assess.align(photo(), [parsed("satellite", 10.0, "2024-09-01", "2025-04-30")])
    assert aligned["covering"] == 1
    assert aligned["closest"] is None
    assert aligned["finest_within_year"] is None


def test_alignment_without_dated_coverage_says_so() -> None:
    aligned = assess.align(photo(), [parsed("old", 0.3, "2018-12-01", "2019-03-01")])
    assert aligned["finest_within_year"] is None
    assert assess.align(photo(), [])["closest"] is None


def test_summary_counts_photos_by_coverage_gap_and_accuracy() -> None:
    aligned = [
        assess.align(photo(id="a"), [parsed("season", 0.25, "2024-12-06", "2025-03-27")]),
        assess.align(photo(id="b", positional_accuracy_m=None), []),
        assess.align(
            photo(id="c", positional_accuracy_m=300.0),
            [parsed("later", 0.075, "2025-12-01", "2025-12-04")],
        ),
    ]
    summary = assess.summarise(aligned)
    assert summary["photos"] == 3
    assert summary["covered"] == 2
    assert summary["captured_inside_window"] == 1
    assert summary["within_year"] == 2
    assert summary["closest_gap_days"] == {"min": 0, "median": 167.5, "max": 335}
    assert summary["accuracy_unknown"] == 1
    assert summary["accuracy_over_20m"] == 1
    assert summary["accuracy_m"] == {"min": 6.0, "median": 153.0, "max": 300.0}


def test_only_public_incidental_photos_are_assessed() -> None:
    photos = [photo(), photo(id="r", cohort="reference"), photo(coordinate_status="obscured")]
    assert [p["id"] for p in assess.assessed_photos(photos)] == ["p1"]


def test_zero_accuracy_is_a_known_accuracy_not_a_missing_one() -> None:
    summary = assess.summarise([assess.align(photo(positional_accuracy_m=0.0), [])])
    assert summary["accuracy_unknown"] == 0


def test_assess_lists_only_collections_that_cover_an_assessed_photo() -> None:
    inside = parsed("season", 0.25, "2024-12-06", "2025-03-27") | {"bands": "rgb"}
    outside = parsed("elsewhere", 0.25, "2024-12-06", "2025-03-27") | {"bands": "rgb"}
    far = {"type": "Polygon", "coordinates": [[[50, 50], [60, 50], [60, 60], [50, 50]]]}
    report = assess.assess([photo()], [(inside, SQUARE), (outside, far)])
    assert [item["slug"] for item in report["collections"]] == ["season"]
    assert report["photos"][0]["closest"]["slug"] == "season"
    assert report["summary"]["captured_inside_window"] == 1


def test_an_undated_photo_is_kept_with_unknown_timing() -> None:
    covering = [parsed("season", 0.25, "2024-12-06", "2025-03-27")]
    aligned = assess.align(photo(observed_on=None), covering)
    assert aligned["covering"] == 1
    assert aligned["closest"] is None
    assert aligned["finest_within_year"] is None
    assert assess.summarise([aligned])["undated"] == 1


def test_a_missing_store_is_an_error_not_an_empty_assessment(tmp_path: Path) -> None:
    with pytest.raises(SystemExit):
        assess.main(["--store", str(tmp_path / "absent")])
    assert not (tmp_path / "absent").exists()


def test_a_run_without_assessable_photos_is_an_error(tmp_path: Path) -> None:
    from weedz.discovery.store import Store

    Store(tmp_path)
    with pytest.raises(SystemExit):
        assess.main(["--store", str(tmp_path), "--run", "missing-run"])
