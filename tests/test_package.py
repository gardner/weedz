"""A follow-up package carries only selected leads, each with its evidence and limits."""

import hashlib
import json
from pathlib import Path

from test_discovery import observation
from test_judgements import PUBLIC, add_finding, load_references, nearby, save, store_with_photo
from test_leads import select
from test_referrals import refer

from weedz.discovery.activities import export
from weedz.discovery.judgements import Judgement
from weedz.discovery.leads import selections
from weedz.discovery.package import follow_up_package
from weedz.discovery.package_report import to_markdown
from weedz.discovery.records import Finding, Photo
from weedz.discovery.source import photo_from_observation
from weedz.discovery.store import Store

WINDOW = [10, 20, 210, 220]
SCREENED = {"best_species": "Clematis vitalba", "width": 400, "height": 300, "box": WINDOW}


def package_of(store: Store) -> dict:
    return follow_up_package(export(store, "run"), selections(store, "run"), "2026-11-14")


def only_lead(store: Store) -> dict:
    [lead] = package_of(store)["leads"]
    return lead


def test_with_no_selection_the_package_says_so(tmp_path: Path) -> None:
    store, _photo_id = store_with_photo(tmp_path, SCREENED)
    package = package_of(store)
    assert package["leads"] == []
    assert "No leads are selected for follow-up" in to_markdown(package)


def test_only_selected_leads_are_packaged(tmp_path: Path) -> None:
    store, photo_id = store_with_photo(tmp_path, SCREENED)
    other = photo_from_observation(observation() | {"id": 7}, "Tasman", "incidental")
    assert other is not None
    store.save_photos("run", [other])
    store.score("run", other.id, SCREENED)
    select(store, photo_id)
    select(store, other.id)
    select(store, other.id, action="deselected", reason="Same patch as a DOC record")
    lead = only_lead(store)
    assert lead["photo_id"] == photo_id
    assert lead["selection"]["selector"] == "Ana"
    assert lead["selection"]["reason"].startswith("Clear leaflets")
    assert [event["action"] for event in lead["selection"]["history"]] == ["selected"]


def test_a_lead_keeps_its_candidate_apart_from_the_original_subject(tmp_path: Path) -> None:
    store, photo_id = store_with_photo(tmp_path, SCREENED)
    store.review("run", photo_id, "confirmed", "", "Ana")
    store.review("run", photo_id, "rejected", "Toetoe", "Ben")
    select(store, photo_id)
    lead = only_lead(store)
    assert lead["candidate"] == {
        "kind": "suggestion",
        "species": "Clematis vitalba",
        "common_name": "Old man's beard",
        "recorded_by": None,
        "note": "",
    }
    assert lead["original_subject"] == {"taxon": "Turdus merula", "common_name": "Blackbird"}
    review = lead["review"]
    assert review["reviewer_decisions"] == {"Ana": "confirmed", "Ben": "rejected"}
    assert review["reviewers_disagree"] is True


def test_judgements_keep_each_opinion_and_their_disagreement(tmp_path: Path) -> None:
    store, photo_id = store_with_photo(tmp_path, SCREENED)
    save(store, photo_id)
    save(store, photo_id, value="disputed", reviewer="Ben", note="Toothed leaflets")
    save(store, photo_id, dimension="history", value="historical_evidence")
    select(store, photo_id)
    judged = only_lead(store)["judgements"]
    assert judged["identity"]["level"] == "disputed"
    assert judged["identity"]["by_reviewer"]["Ben"]["note"] == "Toothed leaflets"
    assert judged["history"]["level"] == "historical_evidence"
    assert judged["novelty"] == {"level": "unassessed", "by_reviewer": {}}
    assert judged["disputed_dimensions"] == ["identity"]


def test_an_obscured_location_is_not_searchable_and_never_revealed(tmp_path: Path) -> None:
    store, photo_id = store_with_photo(tmp_path, SCREENED)  # obscured at -41.2,173.3
    select(store, photo_id)
    package = package_of(store)
    area = package["leads"][0]["limits"]["search_area"]
    assert area["status"] == "obscured" and area["centre"] is None
    assert "-41.2" not in json.dumps(package) and "173.3" not in json.dumps(package)
    assert "not searchable" in to_markdown(package).lower()


def test_a_public_location_gives_a_search_area_and_the_dates_their_limits(tmp_path: Path) -> None:
    store, photo_id = store_with_photo(tmp_path, SCREENED, **PUBLIC)
    select(store, photo_id)
    package = package_of(store)
    limits = package["leads"][0]["limits"]
    assert limits["search_area"]["centre"] == [-41.2, 173.3]
    assert limits["search_area"]["radius_m"] == 200
    assert limits["dates"]["photographed"] == "2024-06-01"
    assert "not that it is there now" in limits["dates"]["current_presence"]
    text = to_markdown(package)
    assert "observation point" in text and "not that it is there now" in text


def test_the_comparison_basis_and_judged_novelty_travel_with_the_lead(tmp_path: Path) -> None:
    store, photo_id = store_with_photo(tmp_path, SCREENED, **PUBLIC)
    snapshot = load_references(tmp_path)
    store.judgement(
        "run",
        photo_id,
        Judgement(dimension="novelty", value="absent_from_references", reviewer="Ana"),
        hashlib.sha256(snapshot.read_bytes()).hexdigest(),
    )
    select(store, photo_id)
    basis = only_lead(store)["comparison"]
    assert basis["snapshot"]["snapshot_sha256"] == hashlib.sha256(snapshot.read_bytes()).hexdigest()
    assert basis["snapshot"]["retrieved_at"] == "2026-11-14"
    assert basis["records_near_photo"]["within_radius"] == 0
    assert basis["judged_novelty"] == "absent_from_references"
    assert basis["judged_against_another_snapshot"] is False
    load_references(
        tmp_path, records=[nearby(2015)]
    )  # a newer snapshot: the judgement now rests on the old one
    assert only_lead(store)["comparison"]["judged_against_another_snapshot"] is True


def test_without_a_snapshot_novelty_against_records_is_unassessed(tmp_path: Path) -> None:
    store, photo_id = store_with_photo(tmp_path, SCREENED, **PUBLIC)
    select(store, photo_id)
    basis = only_lead(store)["comparison"]
    assert basis["snapshot"] is None and basis["records_near_photo"] is None
    assert "unassessed" in basis["note"]


def test_a_recorded_plant_lead_carries_its_own_evidence(tmp_path: Path) -> None:
    store, photo_id = store_with_photo(tmp_path, SCREENED)
    record = {"kind": "addition", "species": "Ulex europaeus", "reviewer": "Ben"}
    store.finding("run", photo_id, Finding.model_validate(record | {"box": [1, 2, 30, 40]}))
    gorse = store.findings("run", photo_id)[-1]["id"]
    typed = add_finding(store, photo_id, species=None)
    save(store, photo_id, finding_id=gorse)
    refer(store, photo_id, finding_id=gorse)
    refer(store, photo_id, finding_id=typed)
    refer(store, photo_id)
    select(store, photo_id, finding_id=gorse)
    lead = only_lead(store)
    assert lead["finding_id"] == gorse
    assert lead["candidate"]["species"] == "Ulex europaeus"
    assert lead["candidate"]["recorded_by"] == "Ben"
    assert lead["judgements"]["identity"]["level"] == "confirmed"
    assert [item["finding_id"] for item in lead["referrals"]] == [gorse, None]
    assert lead["image"]["detail"] == [
        {"box": [1, 2, 30, 40], "is": "Reviewer-drawn visible extent of this plant"}
    ]


def test_a_free_text_plant_is_never_compared_with_records(tmp_path: Path) -> None:
    store, photo_id = store_with_photo(tmp_path, SCREENED, **PUBLIC)
    load_references(tmp_path)
    typed = add_finding(store, photo_id, species=None)
    select(store, photo_id, finding_id=typed)
    lead = only_lead(store)
    assert lead["candidate"]["species"] == "Clematis paniculata"
    assert lead["candidate"]["common_name"] is None
    assert lead["comparison"]["records_near_photo"] is None


def test_an_image_is_packaged_only_when_its_licence_permits(tmp_path: Path) -> None:
    store, photo_id = store_with_photo(tmp_path, SCREENED)
    select(store, photo_id)
    image = only_lead(store)["image"]
    assert image["included"] is True and image["file"] == f"photos/{photo_id}.jpg"
    assert "non-commercial" in image["terms"]
    assert image["detail"][0]["box"] == WINDOW
    saved = Photo.model_validate(store.photos("run")[0])
    store.save_photos("run", [saved.model_copy(update={"photo_license": "cc-by-nd"})])
    image = only_lead(store)["image"]
    assert image["included"] is False and image["file"] is None
    assert "link" in image["terms"].lower()
    lead = only_lead(store)
    assert lead["source"]["url"].startswith("https://www.inaturalist.org/observations/")
    assert lead["source"]["attribution"] == "Example observer (CC BY-NC 4.0)"
