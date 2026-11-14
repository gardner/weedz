"""The collection's gaps are counted from recorded fields; unrecorded ones are said so."""

from typing import Any

from test_reference import note, sample

from weedz.contract import Sample
from weedz.reference import collection

GORSE, CLEMATIS = "Ulex europaeus", "Clematis vitalba"


def photo(number: int, *notes: dict[str, Any], **fields: Any) -> Sample:
    return sample(*notes, id=f"test:{number}", source_id=str(number), **fields)


def test_coverage_counts_photos_with_an_eligible_example_by_recorded_field() -> None:
    samples = [
        photo(1, captured_on="2020-01-10", view="ground", context={"region": "Nelson"}),
        photo(2, note(label="absent"), captured_on="2020-07-10", context={"region": "Tasman"}),
        # Two examples of the same taxon on one photo count it once.
        photo(3, note(), note(id="a2", origin="reviewer", author="Carol")),
    ]
    training = collection("run", samples)["coverage"][GORSE]["training"]
    assert training["photos"] == 3
    assert training["by_label"] == {"present": 2, "absent": 1}
    assert training["by_view"] == {"ground": 1, "unknown": 2}
    assert training["by_season"] == {"DJF": 1, "JJA": 1, "unknown": 1}
    assert training["by_region"] == {"Nelson": 1, "Tasman": 1, "unknown": 1}
    assert training["by_source"] == {"test": 3}


def test_a_declared_species_without_examples_is_a_gap_for_every_use() -> None:
    result = collection("run", [photo(1)], expected=[CLEMATIS])
    assert result["coverage"][CLEMATIS]["evaluation"]["photos"] == 0
    for use in ("training", "evaluation", "sharing"):
        assert f"{CLEMATIS}: no example eligible for {use}" in result["gaps"]


def test_a_species_without_negatives_is_a_gap() -> None:
    gaps = collection("run", [photo(1)])["gaps"]
    assert f"{GORSE}: no absent (negative) example eligible for training" in gaps
    assert f"{GORSE}: no absent (negative) example eligible for evaluation" in gaps


def test_a_source_or_region_in_the_collection_without_the_species_is_a_gap() -> None:
    other = {"source": "other", "id": "other:2", "source_id": "2"}
    samples = [
        photo(1, context={"region": "Nelson"}),
        sample(note(taxon=CLEMATIS), context={"region": "Tasman"}, **other),
    ]
    gaps = collection("run", samples)["gaps"]
    assert f"{GORSE}: no example eligible for training from source: other" in gaps
    assert f"{GORSE}: no example eligible for training from region: Tasman" in gaps


def test_an_unrecorded_viewpoint_or_date_is_unknown_not_a_gap() -> None:
    result = collection("run", [photo(1)])
    unknowns = result["unknowns"]
    assert f"{GORSE}: view is not recorded for any example eligible for training" in unknowns
    assert f"{GORSE}: season is not recorded for any example eligible for training" in unknowns
    assert not any("from view" in gap or "from season" in gap for gap in result["gaps"])


def test_missing_views_and_seasons_are_gaps_once_some_are_recorded() -> None:
    gaps = collection("run", [photo(1, view="ground", captured_on="2020-01-10")])["gaps"]
    assert f"{GORSE}: no example eligible for training from view: nadir, oblique" in gaps
    assert f"{GORSE}: no example eligible for training from season: MAM, JJA, SON" in gaps


def test_growth_stage_and_habitat_are_stated_as_not_recorded() -> None:
    not_recorded = collection("run", [photo(1)])["not_recorded"]
    assert set(not_recorded) == {"growth_stage", "habitat"}
    assert all("not recorded" in reason for reason in not_recorded.values())


def test_examples_without_a_taxon_are_not_a_species() -> None:
    blank = note(supervision="unlabelled", taxon=None, label="unknown")
    assert collection("run", [photo(1, blank)])["coverage"] == {}
