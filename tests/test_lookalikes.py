"""Lookalike photos are screened separately to see how often they pass as weeds."""

from pathlib import Path

import httpx
import pytest
from test_discovery import observation

from weedz.discovery import source
from weedz.discovery.lookalikes import LOOKALIKES, summarize_lookalikes
from weedz.discovery.records import SPECIES, RunSpec
from weedz.discovery.source import Inaturalist, photo_from_observation


def test_every_lookalike_maps_to_a_watchlist_species() -> None:
    assert LOOKALIKES
    assert {entry["confusable_with"] for entry in LOOKALIKES.values()} <= set(SPECIES)
    assert LOOKALIKES[379626]["name"] == "Austroderia"


def test_lookalike_photos_keep_their_cohort_and_confusable_species() -> None:
    photo = photo_from_observation(
        observation(),
        "Nelson",
        "lookalike",
        lookalike_taxon="Austroderia",
        lookalike_of="Cortaderia selloana",
    )
    assert photo is not None
    assert (photo.cohort, photo.lookalike_taxon, photo.lookalike_of) == (
        "lookalike",
        "Austroderia",
        "Cortaderia selloana",
    )
    assert photo.reference_species is None


def test_run_spec_bounds_lookalikes_per_taxon() -> None:
    assert RunSpec().lookalikes_per_taxon == 0
    with pytest.raises(ValueError):
        RunSpec(lookalikes_per_taxon=4)


def test_collect_queries_each_lookalike_taxon_per_region(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(source.time, "sleep", lambda _seconds: None)
    taxa: list[str] = []

    def handle(request: httpx.Request) -> httpx.Response:
        if "taxon_id" in request.url.params and request.url.params["taxon_id"] != "1":
            taxa.append(request.url.params["taxon_id"])
        return httpx.Response(200, json={"results": []})

    client = Inaturalist(tmp_path)
    client.client = httpx.Client(transport=httpx.MockTransport(handle))
    spec = RunSpec(controls_per_species=0, lookalikes_per_taxon=1, sampling="recent")
    client.collect("run", spec)
    assert sorted(taxa) == sorted([str(key) for key in LOOKALIKES] * 2)


def screened(lookalike_of: str, best: str, margins: dict[str, float]) -> dict:
    return {
        "cohort": "lookalike",
        "original_taxon": "Austroderia richardii",
        "lookalike_taxon": "Austroderia",
        "lookalike_of": lookalike_of,
        "scores": {
            "best_species": best,
            "species": [{"name": name, "margin": value} for name, value in margins.items()],
        },
    }


def test_summary_counts_lookalikes_that_pass_as_their_weed() -> None:
    photos = [
        screened("Cortaderia selloana", "Cortaderia selloana", {"Cortaderia selloana": 0.05}),
        screened("Cortaderia selloana", "Ulex europaeus", {"Cortaderia selloana": 0.01}),
        screened("Cortaderia selloana", "Cortaderia selloana", {"Cortaderia selloana": -0.02}),
        {"cohort": "incidental", "scores": {}},
        screened("Cortaderia selloana", "", {}) | {"scores": {}},
    ]
    summary = summarize_lookalikes(photos)
    toetoe = summary["by_taxon"]["Austroderia"]
    assert toetoe["confusable_with"] == "Cortaderia selloana"
    assert toetoe["screened"] == 3
    # The review desk shows the top suggestion whatever its margin, so count it that way.
    assert toetoe["top_suggestion"] == 2
    assert toetoe["positive_confusable_margin"] == 2
    assert toetoe["median_confusable_margin"] == 0.01
    assert "not a reviewed false-positive rate" in summary["meaning"]


def test_export_carries_the_lookalike_summary(tmp_path: Path) -> None:
    from weedz.discovery.activities import export
    from weedz.discovery.store import Store

    store = Store(tmp_path)
    store.create_run("run", RunSpec(lookalikes_per_taxon=1))
    photo = photo_from_observation(
        observation(),
        "Nelson",
        "lookalike",
        lookalike_taxon="Austroderia",
        lookalike_of="Cortaderia selloana",
    )
    assert photo is not None
    store.save_photos("run", [photo])
    store.score(
        "run",
        photo.id,
        {
            "best_species": "Cortaderia selloana",
            "species": [{"name": "Cortaderia selloana", "margin": 0.02}],
        },
    )
    assert export(store, "run")["lookalikes"]["by_taxon"]["Austroderia"]["screened"] == 1


def test_discover_accepts_lookalikes() -> None:
    from weedz.discovery import cli as discovery_cli

    parser_args = ["discover", "--lookalikes", "2"]
    namespace = discovery_cli.parse(parser_args)
    assert namespace.lookalikes == 2


def test_a_top_suggestion_with_a_negative_margin_still_counts_as_suggested() -> None:
    photo = screened("Ulex europaeus", "Ulex europaeus", {"Ulex europaeus": -0.05})
    photo["lookalike_taxon"] = "Cytisus scoparius"
    broom = summarize_lookalikes([photo])["by_taxon"]["Cytisus scoparius"]
    assert (broom["top_suggestion"], broom["positive_confusable_margin"]) == (1, 0)
