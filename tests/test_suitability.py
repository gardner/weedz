"""A run's source suitability: what its incidental photos can and cannot support (P02, P14)."""

from typing import Any

from test_outcomes import photo as base_photo

from weedz.discovery.occurrences import NOT_QUERIED
from weedz.discovery.sharing import WITHHELD
from weedz.discovery.suitability import NOT_MEASURED, suitability
from weedz.discovery.suitability_report import to_markdown

SNAPSHOT = {
    "retrieved_at": "2026-11-14T05:04:00+00:00",
    "dataset": {"title": "DOC weeds"},
    "taxon_keys": {"Ulex europaeus": 1},
}
COMPARED = {"Ulex europaeus": {"comparable": True}}


def photo(pid: str, group: str | None = None, **fields: Any) -> dict[str, Any]:
    """An incidental Nelson photo, screened and compared, under a CC BY licence."""
    defaults = {
        "region": "Nelson",
        "observer": "ana",
        "original_taxon": "Turdus merula",
        "original_common_name": "Blackbird",
        "uploaded_at": "2024-01-02T00:00:00Z",
        "attribution": "Ana (CC BY)",
        "reference_comparison": COMPARED,
        "scores": {"best_species": "Ulex europaeus", "coverage_complete": True},
    }
    return base_photo(pid, group, **(defaults | fields))


def run_export(photos: list[dict[str, Any]], **extra: Any) -> dict[str, Any]:
    incidental = [p for p in photos if p["cohort"] == "incidental"]
    linkable = [p for p in incidental if p["encounter_linkable"]]
    return {
        "run": {
            "id": "run",
            "status": "completed",
            "detail": "",
            "spec": {
                "limit_per_region": 2,
                "sampling": "stratified",
                "after": "2022-01-01",
                "before": "2024-12-31",
            },
        },
        "photos": photos,
        "references": SNAPSHOT,
        "encounters": {
            "rule": "same observer and day",
            "incidental_photos": len(incidental),
            "independent_site_visits": len({p["encounter_group"] for p in linkable}),
            "ungrouped_photos": len(incidental) - len(linkable),
        },
        "corpus_coverage": {
            "sampling": "stratified",
            "photos": len(incidental),
            "by_year": {"2024": len(incidental)},
            "by_season": {"DJF": len(incidental)},
            "undated": 0,
            "observers": 1,
            "observer_days": 1,
        },
        "study": None,
    } | extra


def study(**definition: Any) -> dict[str, Any]:
    return {"id": "study-1", "version": 3, "definition": definition}


def tally(photos: int, visits: int, ungrouped: int) -> dict[str, int]:
    return {"photos": photos, "site_visits": visits, "ungrouped_photos": ungrouped}


def cannot(report: dict[str, Any], key: str) -> dict[str, Any]:
    return next(item for item in report["cannot_support"] if item["key"] == key)


def test_scope_states_shortfalls_and_an_unfinished_run_as_affected_coverage() -> None:
    photos = [photo("a", "a"), photo("b", "b"), photo("c", "c", region="Tasman")]
    photos.append(base_photo("r", None, cohort="reference", region="Nelson"))
    report = suitability(run_export(photos, references=None))
    scope = report["scope"]
    assert scope["incidental"] == tally(3, 3, 0)
    assert scope["other_photos"] == {"reference": 1}
    assert scope["regions"] == {
        "Nelson": {"requested": 2, "photos": 2},
        "Tasman": {"requested": 2, "photos": 1},
    }
    assert any("Tasman returned 1 of 2" in gap for gap in scope["gaps"])
    assert any("No reference snapshot" in gap for gap in scope["gaps"])
    failed = run_export(photos)
    failed["run"] |= {"status": "failed", "detail": "iNaturalist unavailable"}
    assert any(
        "failed" in gap and "iNaturalist unavailable" in gap
        for gap in suitability(failed)["scope"]["gaps"]
    )


def test_dates_are_checked_against_the_study_period_with_empty_years_unassessed() -> None:
    photos = [
        photo("a", "a", observed_on="2024-01-05"),
        photo("b", "b", observed_on="2019-03-01"),
        photo("c", None, observed_on=None),
        photo("d", None, observed_on="2023-06"),
        photo("e", None, observed_on="2021"),
    ]
    linked = study(period_start="2022-01-01", period_end="2024-12-31")
    dates = suitability(run_export(photos, study=linked))["dates"]
    assert dates["study_period"] == {"start": "2022-01-01", "end": "2024-12-31"}
    assert dates["query_period"] == {"start": "2022-01-01", "end": "2024-12-31"}
    assert (dates["earliest"], dates["latest"]) == ("2019-03-01", "2024-01-05")
    # A month or a year is enough when all of it falls on one side of the period.
    assert dates["outside_study_period"] == tally(2, 1, 1)
    assert dates["study_period_unknown"] == tally(1, 0, 1)
    assert dates["undated"] == tally(1, 0, 1)
    assert dates["imprecise"] == tally(2, 0, 2)
    assert dates["years_without_photos"] == [2022]
    # Seasons come from photos inside the period: the 2019 autumn photo does not count.
    assert dates["seasons_without_photos"] == ["MAM", "SON"]


def test_an_imprecise_date_straddling_the_period_start_is_unknown_not_inside() -> None:
    linked = study(period_start="2024-06-01")
    report = suitability(run_export([photo("a", "a", observed_on="2024")], study=linked))
    assert report["dates"]["outside_study_period"] == tally(0, 0, 0)
    assert report["dates"]["study_period_unknown"] == tally(1, 1, 0)
    assert cannot(report, "study_period")["photos"] == tally(1, 1, 0)


def test_without_a_study_the_query_period_bounds_the_years_and_recent_runs_say_so() -> None:
    report = suitability(run_export([photo("a", "a", observed_on="2024-01-05")]))
    assert report["dates"]["study_period"] is None
    assert report["dates"]["years_without_photos"] == [2022, 2023]
    recent = run_export([photo("a", "a", observed_on="2024-01-05")])
    recent["run"]["spec"] = {"limit_per_region": 2, "before": "2024-12-31"}
    dates = suitability(recent)["dates"]
    assert dates["query_period"] == {"start": None, "end": "2024-12-31"}
    assert dates["years_without_photos"] is None
    assert any("before 2024-01-05" in note for note in dates["notes"])


def test_location_quality_gives_reasons_and_the_accuracy_distribution() -> None:
    photos = [
        photo("a", "a", positional_accuracy_m=5.0),
        photo("b", "b", positional_accuracy_m=50.0),
        photo("c", None, positional_accuracy_m=1600.0),
        photo("d", None, positional_accuracy_m=None),
        photo("e", None, coordinate_status="obscured"),
        photo("f", None, coordinate_status="missing", latitude=None, longitude=None),
    ]
    locations = suitability(run_export(photos))["locations"]
    assert locations["search_areas"]["searchable"] == 3
    assert locations["not_searchable"]["obscured"]["photos"] == 1
    assert "obscured" in locations["not_searchable"]["obscured"]["reason"]
    assert set(locations["not_searchable"]) == {"obscured", "missing", "accuracy_unknown"}
    accuracy = locations["accuracy_m"]
    assert (accuracy["reported"], accuracy["not_reported"]) == (3, 1)
    assert (accuracy["min"], accuracy["median"], accuracy["max"]) == (5.0, 50.0, 1600.0)
    assert accuracy["bands"] == {
        "up to 20 m": 1,
        "20 to 100 m": 1,
        "100 to 1,000 m": 0,
        "over 1,000 m": 1,
    }


def test_permitted_uses_give_the_licence_mix_and_what_may_be_shared() -> None:
    photos = [
        photo("a", "a"),
        photo("b", "b", photo_license="cc-by-nc", observation_license="cc-by-nc"),
        photo("c", "c", photo_license="cc-by-nd"),
        photo("d", None, coordinate_status="obscured"),
    ]
    uses = suitability(run_export(photos))["permitted_uses"]
    assert uses["photo_licences"] == {"cc-by": 2, "cc-by-nc": 1, "cc-by-nd": 1}
    assert uses["observation_licences"] == {"cc-by": 3, "cc-by-nc": 1}
    assert uses["non_commercial_only"] == 1
    assert uses["images"] == {"include": 3, "link": 1}
    assert uses["locations"]["shared"] == 3
    assert uses["locations"]["withheld"] == {WITHHELD["obscured"]: 1}


def test_missing_information_is_counted_per_field_including_zeros() -> None:
    photos = [photo("a", "a"), photo("b", None, observed_on=None, sha256="", uploaded_at=None)]
    missing = suitability(run_export(photos))["missing"]
    assert missing["date"] == 1
    assert missing["checksum"] == 1
    assert missing["upload_date"] == 1
    assert missing["source"] == 0
    assert set(missing) >= {"attribution", "licence", "location", "original_subject"}


def test_independence_counts_site_visits_beside_photos() -> None:
    photos = [photo("a", "a"), photo("b", "a"), photo("c", None)]
    independence = suitability(run_export(photos))["independence"]
    assert independence["independent_site_visits"] == 1
    assert independence["ungrouped_photos"] == 1
    assert independence["observer_days"] == 1
    assert independence["rule"] == "same observer and day"


def test_screening_status_keeps_unrecorded_coverage_and_vegetation_explicit() -> None:
    photos = [
        photo("a", "a", scores={"best_species": "U", "coverage_complete": True}),
        photo(
            "b",
            "b",
            scores={"best_species": "U", "coverage_complete": False, "featureless_windows": [3]},
        ),
        photo("c", "c", scores={"best_species": "U"}),
        photo("d", "d", scores={}, review_status="confirmed"),
    ]
    screening = suitability(run_export(photos))["screening"]
    assert screening["screened"] == tally(3, 3, 0)
    assert screening["not_screened"] == tally(1, 1, 0)
    assert screening["pixel_coverage"] == {"complete": 1, "thinned": 1, "not_recorded": 1}
    assert screening["featureless_windows"] == {"photos_with": 1, "not_recorded": 2}
    assert screening["visible_vegetation"] == NOT_MEASURED
    # The literal text, so a placeholder in the constant cannot slip through.
    assert NOT_MEASURED == (
        "Not measured: no step estimates how much vegetation each photo shows. Featureless "
        "windows and pixel coverage say only what the screening could see"
    )
    assert screening["original_subjects"] == {"Blackbird (Turdus merula)": 4}
    assert screening["reviewed"] == tally(1, 1, 0)
    assert screening["unassessed"] == tally(3, 3, 0)


def test_reference_comparison_gives_reasons_or_states_no_snapshot() -> None:
    reason = {"Ulex europaeus": {"comparable": False, "reason": "Photo location is unknown"}}
    photos = [photo("a", "a"), photo("b", None, reference_comparison=reason)]
    compared = suitability(run_export(photos))["reference_comparison"]
    assert compared["snapshot"] == {"retrieved_at": SNAPSHOT["retrieved_at"], "title": "DOC weeds"}
    assert compared["compared"] == tally(1, 1, 0)
    assert compared["not_compared"] == {"Photo location is unknown": tally(1, 0, 1)}
    bare = [photo("a", "a")]
    del bare[0]["reference_comparison"]
    none = suitability(run_export(bare, references=None))["reference_comparison"]
    assert none["snapshot"] is None
    assert list(none["not_compared"]) == ["No reference snapshot to compare against"]


def test_each_conclusion_lists_the_photos_that_cannot_support_it() -> None:
    photos = [
        photo("a", "a"),
        photo("b", None, coordinate_status="obscured", observed_on=None),
        photo("c", "c", positional_accuracy_m=40.0, photo_license="cc-by-sa", scores={}),
    ]
    linked = study(period_start="2024-06-01")
    report = suitability(run_export(photos, study=linked))
    assert [item["key"] for item in report["cannot_support"]] == [
        "field_search",
        "site_context",
        "history",
        "study_period",
        "novelty",
        "independent_count",
        "shared_image",
        "shared_location",
        "screening",
    ]
    assert cannot(report, "field_search")["photos"] == tally(1, 0, 1)
    assert cannot(report, "site_context")["photos"] == tally(2, 1, 1)
    assert cannot(report, "history")["photos"] == tally(1, 0, 1)
    # The undated photo cannot be placed in the period either.
    assert cannot(report, "study_period")["photos"] == tally(3, 2, 1)
    assert cannot(report, "independent_count")["photos"] == tally(1, 0, 1)
    assert cannot(report, "shared_image")["photos"] == tally(1, 1, 0)
    assert cannot(report, "shared_location")["photos"] == tally(1, 0, 1)
    assert cannot(report, "screening")["photos"] == tally(1, 1, 0)
    for item in report["cannot_support"]:
        assert item["conclusion"] and item["because"]


def test_without_a_study_the_study_period_conclusion_is_not_assessed() -> None:
    report = suitability(run_export([photo("a", "a")]))
    period = cannot(report, "study_period")
    assert period["photos"] is None
    assert "No study period" in period["because"]
    assert report["study"] is None


def test_a_linked_study_is_named_with_its_differences_from_the_screening() -> None:
    linked = study(regions=[{"name": "Nelson"}], watchlist=[{"species": "Ulex europaeus"}])
    report = suitability(run_export([photo("a", "a")], study=linked))
    assert report["study"]["id"] == "study-1"
    assert report["study"]["version"] == 3
    assert report["study"]["regions"] == ["Nelson"]
    assert any("Tasman" in note for note in report["study"]["differences"])


def test_markdown_states_unknowns_and_never_implies_weed_free() -> None:
    photos = [photo("a", "a"), photo("b", None, observed_on=None, coordinate_status="obscured")]
    text = to_markdown(suitability(run_export(photos, references=None)))
    assert text.startswith("# Source suitability: run")
    assert "not evidence that no weed is there" in text
    assert f"Visible vegetation: {NOT_MEASURED}" in text
    assert "| A field search lead |" in text
    assert "1 site visit + 1 ungrouped photo (2 photos)" in text
    assert "No reference snapshot" in text
    assert "the snapshot did not query: Clematis vitalba, Cortaderia selloana" in text


def test_a_photo_reason_outranks_a_species_the_snapshot_did_not_query() -> None:
    found = {
        "Clematis vitalba": {"comparable": False, "reason": NOT_QUERIED},
        "Ulex europaeus": {"comparable": False, "reason": "Photo location accuracy is unknown"},
    }
    compared = suitability(run_export([photo("a", None, reference_comparison=found)]))
    result = compared["reference_comparison"]
    assert list(result["not_compared"]) == ["Photo location accuracy is unknown"]
    # The fixture snapshot queried only gorse; the rest are named, never assumed absent.
    assert result["not_queried_species"] == ["Clematis vitalba", "Cortaderia selloana"]
