"""Photos from one site visit are related evidence, not independent discoveries."""

from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient
from test_discovery import observation

from weedz.discovery.activities import export
from weedz.discovery.api import create_app
from weedz.discovery.encounters import RULE, encounter_groups, summarize
from weedz.discovery.records import RunSpec
from weedz.discovery.source import photo_from_observation
from weedz.discovery.store import Store


def photo(photo_id: str, **overrides: Any) -> dict[str, Any]:
    return {
        "id": photo_id,
        "cohort": "incidental",
        "observer": "ana",
        "observed_on": "2024-12-30",
        "latitude": -41.2637,
        "longitude": 173.2880,
        "positional_accuracy_m": 5.0,
        "coordinate_status": "public",
    } | overrides


# Roughly 111 m per 0.001 degrees of latitude.
def test_nearby_photos_on_one_visit_share_a_group() -> None:
    groups = encounter_groups([photo("b"), photo("a", latitude=-41.2638)])
    assert groups == {"a": "a", "b": "a"}


def test_groups_chain_through_intermediate_photos() -> None:
    photos = [
        photo("a", latitude=-41.2600),
        photo("b", latitude=-41.2620),
        photo("c", latitude=-41.2640),
    ]
    assert set(encounter_groups(photos).values()) == {"a"}


def test_distant_photos_are_separate_unless_accuracy_overlaps() -> None:
    far = [photo("a", latitude=-41.2600), photo("b", latitude=-41.2650)]
    assert len(set(encounter_groups(far).values())) == 2
    vague = [
        photo("a", latitude=-41.2600, positional_accuracy_m=200.0),
        photo("b", latitude=-41.2650, positional_accuracy_m=200.0),
    ]
    assert len(set(encounter_groups(vague).values())) == 1


def test_different_day_or_observer_is_a_different_visit() -> None:
    assert encounter_groups([photo("a"), photo("b", observed_on="2024-12-31")])["b"] == "b"
    assert encounter_groups([photo("a"), photo("b", observer="ben")])["b"] == "b"


def test_unknown_or_obscured_evidence_never_invents_a_link() -> None:
    photos = [
        photo("a"),
        photo("b", coordinate_status="obscured"),
        photo("c", latitude=None, longitude=None, coordinate_status="missing"),
        photo("d", observed_on=None),
    ]
    assert encounter_groups(photos) == {"a": "a", "b": "b", "c": "c", "d": "d"}


def test_summary_counts_independent_incidental_visits() -> None:
    photos = [photo("a"), photo("b"), photo("c", observer="ben"), photo("r", cohort="reference")]
    summary = summarize(photos, encounter_groups(photos))
    assert summary == {"rule": RULE, "incidental_photos": 3, "independent_site_visits": 2}


def test_api_and_export_report_site_visits(tmp_path: Path) -> None:
    store = Store(tmp_path)
    store.create_run("run", RunSpec())
    public = observation() | {"obscured": False}
    first = photo_from_observation(public, "Nelson", "incidental")
    second = photo_from_observation(public | {"id": 200}, "Nelson", "incidental")
    assert first is not None and second is not None
    store.save_photos("run", [first, second])
    detail = TestClient(create_app(tmp_path)).get("/runs/run").json()
    assert {item["encounter_size"] for item in detail["photos"]} == {2}
    assert len({item["encounter_group"] for item in detail["photos"]}) == 1
    assert export(store, "run")["encounters"]["independent_site_visits"] == 1
    assert all("encounter_group" in item for item in export(store, "run")["photos"])
