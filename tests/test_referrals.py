"""Unresolved findings are referred for specialist assessment and tracked until closed."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from test_discovery import observation
from test_judgements import add_finding, save, store_with_photo

from weedz.discovery.activities import export
from weedz.discovery.api import create_app
from weedz.discovery.audit import audit_sample
from weedz.discovery.records import RunSpec
from weedz.discovery.referrals import REASONS, Referral, ReferralEvent
from weedz.discovery.source import photo_from_observation
from weedz.discovery.store import Store


def referral(**fields: object) -> dict:
    base = {"reason": "lookalike", "note": "Could be native Clematis paniculata"}
    return base | {"expertise": "Clematis specialist", "referrer": "Ana"} | fields


def answer(**fields: object) -> dict:
    return {
        "action": "answered",
        "actor": "Dr Wiri",
        "note": "Leaflet margins say vitalba",
    } | fields


def refer(store: Store, photo_id: str, **fields: object) -> int:
    return store.refer("run", photo_id, Referral.model_validate(referral(**fields)))


def test_a_referral_needs_a_known_reason_and_a_note() -> None:
    assert set(REASONS) == {
        "lookalike",
        "cultivated_or_wild",
        "poor_view",
        "location_or_date",
        "other",
    }
    with pytest.raises(ValidationError):
        Referral.model_validate(referral(reason="hunch"))
    with pytest.raises(ValidationError, match="what is unresolved"):
        Referral.model_validate(referral(note="  "))
    with pytest.raises(ValidationError):
        Referral.model_validate(referral(referrer=" "))
    assert Referral.model_validate(referral(expertise="")).expertise == ""


def test_closing_a_referral_needs_a_name_and_a_note() -> None:
    with pytest.raises(ValidationError):
        ReferralEvent.model_validate(answer(action="edited"))
    with pytest.raises(ValidationError, match="note"):
        ReferralEvent.model_validate(answer(note=""))
    with pytest.raises(ValidationError):
        ReferralEvent.model_validate(answer(actor=""))
    with pytest.raises(ValidationError, match="Only an answer"):
        ReferralEvent.model_validate(answer(action="withdrawn", judgement_ids=[1]))


def test_a_referral_stays_open_until_answered_and_is_never_edited(tmp_path: Path) -> None:
    store, photo_id = store_with_photo(tmp_path)
    first = refer(store, photo_id, effort_seconds=30)
    [photo] = store.photos("run")
    [open_referral] = photo["referrals"]
    assert open_referral["id"] == first
    assert (open_referral["status"], open_referral["finding_id"]) == ("open", None)
    assert open_referral["events"] == []
    store.close_referral("run", photo_id, first, ReferralEvent.model_validate(answer()))
    [answered] = store.photos("run")[0]["referrals"]
    assert answered["status"] == "answered"
    assert answered["note"] == "Could be native Clematis paniculata", "the referral is kept"
    [event] = answered["events"]
    assert (event["action"], event["actor"]) == ("answered", "Dr Wiri")
    # The reviewer's decision is not touched by the specialist's answer.
    assert store.photos("run")[0]["review_status"] == "unreviewed"


def test_only_an_open_referral_can_be_closed(tmp_path: Path) -> None:
    store, photo_id = store_with_photo(tmp_path)
    first = refer(store, photo_id)
    withdrawn = ReferralEvent.model_validate(
        answer(action="withdrawn", actor="Ana", note="Second photo settles it")
    )
    store.close_referral("run", photo_id, first, withdrawn)
    with pytest.raises(ValueError, match="already withdrawn"):
        store.close_referral("run", photo_id, first, ReferralEvent.model_validate(answer()))
    with pytest.raises(KeyError):
        store.close_referral("run", photo_id, first + 99, withdrawn)
    assert store.photos("run")[0]["referrals"][0]["status"] == "withdrawn"


def test_a_recorded_plant_can_be_referred_on_its_own(tmp_path: Path) -> None:
    store, photo_id = store_with_photo(tmp_path)
    gorse = add_finding(store, photo_id)
    refer(store, photo_id, finding_id=gorse, reason="cultivated_or_wild")
    [photo] = store.photos("run")
    assert photo["referrals"][0]["finding_id"] == gorse


def test_an_answer_can_point_to_the_judgements_it_informed(tmp_path: Path) -> None:
    store, photo_id = store_with_photo(tmp_path)
    gorse = add_finding(store, photo_id)
    save(store, photo_id, reviewer="Dr Wiri", note="before the referral")
    referred = refer(store, photo_id, finding_id=gorse)
    save(store, photo_id, reviewer="Dr Wiri", value="disputed", finding_id=gorse)
    save(store, photo_id, reviewer="Dr Wiri", value="disputed")
    client = TestClient(create_app(tmp_path))
    path = f"/runs/run/photos/{photo_id}/referrals/{referred}/events"
    ids = [row["id"] for row in store.judgements("run", photo_id)]
    # Only judgements on the referred plant, made since it was referred, can be cited.
    for wrong in (ids[0], ids[2], 999):
        response = client.post(path, json=answer(judgement_ids=[wrong]))
        assert response.status_code == 409, wrong
    assert client.post(path, json=answer(judgement_ids=[ids[1]])).status_code == 200
    [event] = store.photos("run")[0]["referrals"][0]["events"]
    assert event["judgement_ids"] == [ids[1]]
    # Standing judgements carry their id so an answer can cite them.
    plant = store.photos("run")[0]["findings"][0]
    assert plant["judgements"]["identity"]["Dr Wiri"]["id"] == ids[1]


def test_api_refers_lists_and_closes_referrals(tmp_path: Path) -> None:
    store, photo_id = store_with_photo(tmp_path)
    client = TestClient(create_app(tmp_path))
    path = f"/runs/run/photos/{photo_id}/referrals"
    assert client.post(path, json=referral(effort_seconds=12.5)).status_code == 200
    [saved] = client.get(path).json()
    assert (saved["reason"], saved["status"], saved["effort_seconds"]) == (
        "lookalike",
        "open",
        12.5,
    )
    events = f"{path}/{saved['id']}/events"
    assert client.post(events, json=answer(effort_seconds=40)).status_code == 200
    assert client.post(events, json=answer()).status_code == 409
    assert client.get(path).json()[0]["status"] == "answered"
    assert client.get("/runs/run").json()["photos"][0]["referrals"][0]["status"] == "answered"
    assert client.post(f"{path}/999/events", json=answer()).status_code == 404
    assert client.post("/runs/run/photos/missing/referrals", json=referral()).status_code == 404
    assert client.get("/runs/run/photos/missing/referrals").status_code == 404
    assert client.post(path, json=referral(reason="hunch")).status_code == 422
    assert client.post(path, json=referral(finding_id=42)).status_code == 404


def test_a_referral_is_closed_only_through_its_own_photo(tmp_path: Path) -> None:
    store, photo_id = store_with_photo(tmp_path)
    referred = refer(store, photo_id)
    other = photo_from_observation(observation() | {"id": 999}, "Nelson", "incidental")
    assert other is not None
    store.save_photos("run", [other])
    client = TestClient(create_app(tmp_path))
    response = client.post(
        f"/runs/run/photos/{other.id}/referrals/{referred}/events", json=answer()
    )
    assert response.status_code == 404


def test_export_carries_referral_history_and_counts_its_time(tmp_path: Path) -> None:
    store, photo_id = store_with_photo(tmp_path)
    referred = refer(store, photo_id, effort_seconds=60)
    store.close_referral(
        "run", photo_id, referred, ReferralEvent.model_validate(answer(effort_seconds=120))
    )
    refer(store, photo_id, reason="poor_view")
    result = export(store, "run")
    [entry] = result["review_history"]
    assert [row["status"] for row in entry["referrals"]] == ["answered", "open"]
    assert entry["referrals"][0]["events"][0]["actor"] == "Dr Wiri"
    effort = result["review_effort"]
    assert effort["total_minutes"] == 3.0
    assert effort["minutes_by_referral_action"] == {"referred": 1.0, "answered": 2.0}
    assert effort["minutes_by_reviewer"] == {"Ana": 1.0, "Dr Wiri": 2.0}
    assert (effort["measured_referral_actions"], effort["unmeasured_referral_actions"]) == (2, 1)
    assert effort["unmeasured_incidental_referral_actions"] == 1
    assert any("Referrals" in line for line in result["limitations"])


def test_a_referral_by_someone_who_had_not_audited_unblinds_later_audits(
    tmp_path: Path,
) -> None:
    store = Store(tmp_path)
    store.create_run("run", RunSpec())
    records = [
        photo_from_observation(observation() | {"id": 100 + index}, "Nelson", "incidental")
        for index in range(8)
    ]
    store.save_photos("run", [record for record in records if record is not None])
    target, answered = sorted(audit_sample("run", store.photos("run")))[:2]
    refer(store, target, referrer="Carol")
    # Answering, too, means the specialist saw the suggestion.
    store.audit("run", answered, "none", "", "Ben")
    referred = refer(store, answered, referrer="Ben")
    store.close_referral("run", answered, referred, ReferralEvent.model_validate(answer()))
    store.audit("run", target, "Ulex europaeus", "", "Ana")
    store.audit("run", answered, "Ulex europaeus", "", "Dr Wiri")
    assert store.latest_audits("run") == {answered: {"Ben": "none"}}
    assert store.latest_audits("run", blind=False) == {
        target: {"Ana": "Ulex europaeus"},
        answered: {"Dr Wiri": "Ulex europaeus"},
    }
