"""Leads worth follow-up are selected by name, with a reason, and never edited."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from test_discovery import observation
from test_judgements import add_finding, store_with_photo

from weedz.discovery.activities import export
from weedz.discovery.api import create_app
from weedz.discovery.audit import audit_sample
from weedz.discovery.leads import LeadEvent, record_lead, selected_leads, selections
from weedz.discovery.records import RunSpec
from weedz.discovery.source import photo_from_observation
from weedz.discovery.store import Store


def event(**fields: object) -> dict:
    base = {"action": "selected", "selector": "Ana"}
    return base | {"reason": "Clear leaflets beside a stream; worth a site visit"} | fields


def select(store: Store, photo_id: str, **fields: object) -> None:
    record_lead(store, "run", photo_id, LeadEvent.model_validate(event(**fields)))


def test_a_selection_needs_a_name_a_reason_and_a_known_action() -> None:
    with pytest.raises(ValidationError, match="why"):
        LeadEvent.model_validate(event(reason="  "))
    with pytest.raises(ValidationError):
        LeadEvent.model_validate(event(selector=""))
    with pytest.raises(ValidationError):
        LeadEvent.model_validate(event(action="edited"))


def test_selections_are_appended_and_the_latest_event_stands(tmp_path: Path) -> None:
    store, photo_id = store_with_photo(tmp_path)
    gorse = add_finding(store, photo_id)
    select(store, photo_id)
    select(store, photo_id, finding_id=gorse, selector="Ben", reason="Gorse in the background")
    select(store, photo_id, action="deselected", reason="Same plant as an existing DOC record")
    history = selections(store, "run")
    assert [(row["action"], row["finding_id"]) for row in history] == [
        ("selected", None),
        ("selected", gorse),
        ("deselected", None),
    ]
    [lead] = selected_leads(history)
    assert (lead["finding_id"], lead["selector"]) == (gorse, "Ben")
    assert lead["reason"] == "Gorse in the background"
    assert [row["action"] for row in lead["history"]] == ["selected"]


def test_a_deselected_lead_keeps_its_history_when_selected_again(tmp_path: Path) -> None:
    store, photo_id = store_with_photo(tmp_path)
    select(store, photo_id)
    select(store, photo_id, action="deselected", reason="Wait for the specialist")
    select(store, photo_id, selector="Carol", reason="Specialist confirmed vitalba")
    [lead] = selected_leads(selections(store, "run"))
    assert (lead["selector"], lead["reason"]) == ("Carol", "Specialist confirmed vitalba")
    assert [row["action"] for row in lead["history"]] == ["selected", "deselected", "selected"]


def test_the_api_records_selections_and_refuses_what_cannot_change(tmp_path: Path) -> None:
    store, photo_id = store_with_photo(tmp_path)
    client = TestClient(create_app(tmp_path))
    path = f"/runs/run/photos/{photo_id}/leads"
    assert client.post(path, json=event(action="deselected")).status_code == 409
    assert client.post(path, json=event()).status_code == 200
    assert client.post(path, json=event()).status_code == 409, "already selected"
    assert client.post(path, json=event(finding_id=999)).status_code == 404
    assert client.post("/runs/run/photos/missing/leads", json=event()).status_code == 404
    assert client.post(path, json=event(reason="")).status_code == 422
    photo = client.get("/runs/run").json()["photos"][0]
    assert photo["lead"]["suggestion"]["selector"] == "Ana"
    plant = add_finding(store, photo_id)
    assert client.post(path, json=event(finding_id=plant)).status_code == 200
    photo = client.get("/runs/run").json()["photos"][0]
    assert photo["lead"]["plants"][str(plant)]["reason"].startswith("Clear leaflets")


def test_only_screened_incidental_plants_can_be_leads(tmp_path: Path) -> None:
    store, photo_id = store_with_photo(tmp_path, scores=None)
    client = TestClient(create_app(tmp_path))
    path = f"/runs/run/photos/{photo_id}/leads"
    assert client.post(path, json=event()).status_code == 409, "no suggestion to select"
    reference = photo_from_observation(observation() | {"id": 5}, "Nelson", "reference")
    assert reference is not None
    store.save_photos("run", [reference])
    reference_path = f"/runs/run/photos/{reference.id}/leads"
    assert client.post(reference_path, json=event()).status_code == 409


def test_a_selection_by_someone_who_had_not_audited_unblinds_later_audits(
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
    select(store, target, selector="Carol")
    store.audit("run", target, "Ulex europaeus", "", "Ana")
    assert store.latest_audits("run") == {}


def test_the_run_export_keeps_every_selection_event(tmp_path: Path) -> None:
    store, photo_id = store_with_photo(tmp_path)
    select(store, photo_id)
    select(store, photo_id, action="deselected", reason="Matches a DOC record")
    result = export(store, "run")
    assert [row["action"] for row in result["lead_selections"]] == ["selected", "deselected"]
    assert any("follow-up" in line for line in result["limitations"])
