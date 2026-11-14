"""Identity, location usefulness, historical relevance and novelty are judged separately."""

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from test_discovery import observation

from weedz.discovery.activities import export
from weedz.discovery.api import create_app
from weedz.discovery.audit import audit_sample
from weedz.discovery.judgements import JUDGEMENTS, Judgement
from weedz.discovery.occurrences import TAXON_KEYS
from weedz.discovery.records import Finding, RunSpec
from weedz.discovery.source import photo_from_observation
from weedz.discovery.store import Store

PUBLIC = {"obscured": False, "geoprivacy": None}
SCREENED = {"best_species": "Clematis vitalba", "width": 400, "height": 300}


def store_with_photo(
    root: Path, scores: dict | None = SCREENED, **fields: object
) -> tuple[Store, str]:
    store = Store(root)
    store.create_run("run", RunSpec())
    photo = photo_from_observation(observation() | fields, "Nelson", "incidental")
    assert photo is not None
    store.save_photos("run", [photo])
    if scores:
        store.score("run", photo.id, scores)
    return store, photo.id


def add_finding(store: Store, photo_id: str, species: str | None = "Ulex europaeus") -> int:
    taxon = {"species": species} if species else {"other_taxon": "Clematis paniculata"}
    record = {"kind": "addition", "reviewer": "Ben"} | taxon
    store.finding("run", photo_id, Finding.model_validate(record))
    return store.findings("run", photo_id)[-1]["id"]


def judgement(**fields: object) -> dict:
    return {"dimension": "identity", "value": "confirmed", "reviewer": "Ana"} | fields


def save(store: Store, photo_id: str, **fields: object) -> None:
    store.judgement("run", photo_id, Judgement.model_validate(judgement(**fields)))


def load_references(root: Path, taxon_keys: dict[str, int] = TAXON_KEYS) -> None:
    folder = root / "references"
    folder.mkdir()
    snapshot = {"retrieved_at": "2026-11-14", "records": [], "taxon_keys": taxon_keys}
    (folder / "doc-weeds-20261114T000000Z.json").write_text(json.dumps(snapshot))


def test_every_dimension_has_an_explicit_unassessed_value() -> None:
    assert set(JUDGEMENTS) == {"identity", "location", "history", "novelty"}
    assert all("unassessed" in values for values in JUDGEMENTS.values())
    assert {"new_in_photo", "absent_from_references", "earlier_than_records"} < set(
        JUDGEMENTS["novelty"]
    )
    assert {"usable", "too_imprecise", "camera_point_only", "unknown"} < set(JUDGEMENTS["location"])


def test_a_value_must_belong_to_its_dimension() -> None:
    assert Judgement.model_validate(judgement(dimension="location", value="camera_point_only"))
    for invalid in [
        judgement(value="usable"),
        judgement(dimension="species"),
        judgement(dimension="novelty", value="new"),
        judgement(reviewer=" "),
    ]:
        with pytest.raises(ValidationError):
            Judgement.model_validate(invalid)


def test_a_verified_new_locality_needs_its_verification_evidence() -> None:
    verified = judgement(dimension="novelty", value="verified_new_locality")
    for note in ["", "   "]:
        with pytest.raises(ValidationError, match="verification"):
            Judgement.model_validate(verified | {"note": note})
    note = "Site visit by J. Doe on 2026-10-02; DOC Nelson confirmed no prior record"
    assert Judgement.model_validate(verified | {"note": note}).note == note


def test_unresolved_identity_and_reported_absence_need_a_reason() -> None:
    for dimension, value in [("identity", "unresolved"), ("history", "no_longer_present")]:
        with pytest.raises(ValidationError):
            Judgement.model_validate(judgement(dimension=dimension, value=value))
        assert Judgement.model_validate(judgement(dimension=dimension, value=value, note="Why"))


def test_judgements_are_appended_and_each_dimension_stands_alone(tmp_path: Path) -> None:
    store, photo_id = store_with_photo(tmp_path, **PUBLIC)
    save(store, photo_id, note="Leaflets toothed", effort_seconds=20)
    save(store, photo_id, dimension="location", value="camera_point_only")
    save(store, photo_id, dimension="identity", value="disputed", reviewer="Ben")
    history = store.judgements("run", photo_id)
    assert [(row["dimension"], row["value"], row["reviewer"]) for row in history] == [
        ("identity", "confirmed", "Ana"),
        ("location", "camera_point_only", "Ana"),
        ("identity", "disputed", "Ben"),
    ]
    assert history[0]["note"] == "Leaflets toothed" and history[0]["created_at"]
    [photo] = store.photos("run")
    standing = photo["judgements"]
    assert {name: value["value"] for name, value in standing["identity"].items()} == {
        "Ana": "confirmed",
        "Ben": "disputed",
    }
    assert standing["identity"]["Ana"]["note"] == "Leaflets toothed"
    assert list(standing["location"]) == ["Ana"]
    assert standing["history"] == {} and standing["novelty"] == {}
    assert photo["judgement_disputes"] == ["identity"]
    # The suggestion decision is untouched.
    assert photo["review_status"] == "unreviewed" and photo["review_count"] == 0


def test_the_latest_judgement_stands_and_unassessed_withdraws_it(tmp_path: Path) -> None:
    store, photo_id = store_with_photo(tmp_path)
    save(store, photo_id, reviewer="Ben", value="disputed")
    save(store, photo_id)
    save(store, photo_id, reviewer="Ben")
    assert store.photos("run")[0]["judgement_disputes"] == []
    save(store, photo_id, reviewer="Ben", value="unassessed")
    assert list(store.photos("run")[0]["judgements"]["identity"]) == ["Ana"]
    assert len(store.judgements("run", photo_id)) == 4


def test_claims_the_photo_cannot_support_are_refused(tmp_path: Path) -> None:
    _store, photo_id = store_with_photo(tmp_path, observed_on=None)
    client = TestClient(create_app(tmp_path))
    path = f"/runs/run/photos/{photo_id}/judgements"
    refused = [
        judgement(dimension="location", value="usable"),
        judgement(dimension="history", value="recent_evidence"),
        judgement(dimension="history", value="historical_evidence"),
        judgement(dimension="novelty", value="absent_from_references"),
        judgement(dimension="novelty", value="earlier_than_records"),
    ]
    for body in refused:
        response = client.post(path, json=body)
        assert response.status_code == 409, body
        assert response.json()["detail"]
    for body in [
        judgement(dimension="location", value="too_imprecise"),
        judgement(dimension="history", value="date_unknown"),
        judgement(dimension="novelty", value="unassessed"),
        judgement(dimension="novelty", value="new_in_photo"),
    ]:
        assert client.post(path, json=body).status_code == 200, body


def test_record_relative_novelty_needs_a_comparable_reference_snapshot(tmp_path: Path) -> None:
    _store, photo_id = store_with_photo(tmp_path, **PUBLIC)
    client = TestClient(create_app(tmp_path))
    path = f"/runs/run/photos/{photo_id}/judgements"
    absent = judgement(dimension="novelty", value="absent_from_references")
    assert client.post(path, json=absent).status_code == 409
    load_references(tmp_path)
    assert client.post(path, json=absent).status_code == 200
    earlier = judgement(dimension="novelty", value="earlier_than_records")
    assert client.post(path, json=earlier).status_code == 200
    usable = judgement(dimension="location", value="usable")
    assert client.post(path, json=usable).status_code == 200


def test_an_obscured_photo_cannot_be_compared_with_records(tmp_path: Path) -> None:
    _store, photo_id = store_with_photo(tmp_path)
    load_references(tmp_path)
    client = TestClient(create_app(tmp_path))
    path = f"/runs/run/photos/{photo_id}/judgements"
    body = judgement(dimension="novelty", value="absent_from_references")
    assert client.post(path, json=body).status_code == 409


def test_api_records_lists_and_details_judgements(tmp_path: Path) -> None:
    _store, photo_id = store_with_photo(tmp_path)
    client = TestClient(create_app(tmp_path))
    path = f"/runs/run/photos/{photo_id}/judgements"
    assert client.post(path, json=judgement(effort_seconds=12.5, note="n")).status_code == 200
    [saved] = client.get(path).json()
    assert (saved["value"], saved["note"], saved["effort_seconds"]) == ("confirmed", "n", 12.5)
    photo = client.get("/runs/run").json()["photos"][0]
    assert photo["judgements"]["identity"]["Ana"]["value"] == "confirmed"
    assert client.post("/runs/run/photos/missing/judgements", json=judgement()).status_code == 404
    assert client.get("/runs/run/photos/missing/judgements").status_code == 404
    unverified = judgement(dimension="novelty", value="verified_new_locality")
    assert client.post(path, json=unverified).status_code == 422


def test_export_carries_judgement_history_and_counts_their_time(tmp_path: Path) -> None:
    store, photo_id = store_with_photo(tmp_path)
    save(store, photo_id, effort_seconds=60)
    save(store, photo_id, dimension="location", value="unknown", reviewer="Ben")
    result = export(store, "run")
    [entry] = result["review_history"]
    assert [row["dimension"] for row in entry["judgements"]] == ["identity", "location"]
    assert result["photos"][0]["judgements"]["location"]["Ben"]["value"] == "unknown"
    effort = result["review_effort"]
    assert effort["total_minutes"] == 1.0
    assert effort["minutes_by_judgement_dimension"] == {"identity": 1.0}
    assert (effort["measured_judgements"], effort["unmeasured_judgements"]) == (1, 1)
    assert effort["unmeasured_incidental_judgements"] == 1
    assert any("Judgements" in line for line in result["limitations"])


def test_a_judgement_by_someone_who_had_not_audited_unblinds_later_audits(
    tmp_path: Path,
) -> None:
    store = Store(tmp_path)
    store.create_run("run", RunSpec())
    records = [
        photo_from_observation(observation() | {"id": 100 + index}, "Nelson", "incidental")
        for index in range(8)
    ]
    store.save_photos("run", [record for record in records if record is not None])
    target = sorted(audit_sample("run", store.photos("run")))[0]
    save(store, target, reviewer="Carol")
    store.audit("run", target, "Ulex europaeus", "", "Ana")
    assert store.latest_audits("run") == {}
    assert store.latest_audits("run", blind=False) == {target: {"Ana": "Ulex europaeus"}}


def test_a_recorded_plant_is_judged_apart_from_the_suggestion(tmp_path: Path) -> None:
    store, photo_id = store_with_photo(tmp_path)
    gorse = add_finding(store, photo_id)
    save(store, photo_id, dimension="novelty", value="new_in_photo", finding_id=gorse)
    save(store, photo_id, dimension="novelty", value="already_recorded")
    [photo] = store.photos("run")
    assert photo["judgements"]["novelty"]["Ana"]["value"] == "already_recorded"
    [plant] = photo["findings"]
    assert plant["judgements"]["novelty"]["Ana"]["value"] == "new_in_photo"
    assert plant["judgement_disputes"] == [] and photo["judgement_disputes"] == []
    assert [row["finding_id"] for row in store.judgements("run", photo_id)] == [gorse, None]
    assert export(store, "run")["photos"][0]["findings"][0]["judgements"] == plant["judgements"]


def test_a_judgement_targets_the_suggestion_or_one_of_the_photos_plants(tmp_path: Path) -> None:
    store, photo_id = store_with_photo(tmp_path, scores=None)
    client = TestClient(create_app(tmp_path))
    path = f"/runs/run/photos/{photo_id}/judgements"
    # Unscreened: there is no suggestion to judge, only recorded plants.
    assert client.post(path, json=judgement()).status_code == 409
    plant = add_finding(store, photo_id)
    assert client.post(path, json=judgement(finding_id=plant)).status_code == 200
    assert client.post(path, json=judgement(finding_id=plant + 1)).status_code == 404


def test_novelty_against_records_needs_the_judged_plant_compared(tmp_path: Path) -> None:
    store, photo_id = store_with_photo(tmp_path, **PUBLIC)
    # The snapshot queried gorse only, so the suggested old man's beard was not compared.
    load_references(tmp_path, {"Ulex europaeus": TAXON_KEYS["Ulex europaeus"]})
    gorse, typed = add_finding(store, photo_id), add_finding(store, photo_id, species=None)
    client = TestClient(create_app(tmp_path))
    path = f"/runs/run/photos/{photo_id}/judgements"
    for value in ["absent_from_references", "earlier_than_records"]:
        claim = judgement(dimension="novelty", value=value)
        assert client.post(path, json=claim).status_code == 409, value
        # Free text names no taxon the records were checked against.
        assert client.post(path, json=claim | {"finding_id": typed}).status_code == 409, value
        assert client.post(path, json=claim | {"finding_id": gorse}).status_code == 200, value
