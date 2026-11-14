"""Approved device reports reach specialist review in their own run (issue #58)."""

import hashlib
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from intake_helpers import jpeg, new_id, report, with_image

from weedz.discovery.api import create_app
from weedz.discovery.device_reports import RUN_ID, sync
from weedz.discovery.sharing import image_use
from weedz.discovery.store import Store
from weedz.intake.api import IntakeAPI
from weedz.intake.limits import Limits
from weedz.intake.store import ReportStore


def send(intake: Path, body: dict, submitter: int = 1) -> str:
    """Receive a report as the intake API would, and return its id."""
    report_id = new_id()
    IntakeAPI(intake, Limits()).accept(submitter, report_id, json.dumps(body).encode())
    return report_id


def synced(root: Path, intake: Path) -> list[dict]:
    store = Store(root / "pilot")
    sync(store, ReportStore(intake))
    return store.photos(RUN_ID)


@pytest.fixture
def intake(tmp_path: Path) -> Path:
    return tmp_path / "intake"


@pytest.fixture
def client(tmp_path: Path, intake: Path) -> TestClient:
    return TestClient(create_app(tmp_path / "pilot", intake_dir=intake))


def detail(client: TestClient) -> dict:
    response = client.get(f"/runs/{RUN_ID}")
    assert response.status_code == 200, response.text
    return response.json()


def test_a_report_becomes_a_review_item_with_its_provenance(tmp_path: Path, intake: Path) -> None:
    body = with_image(jpeg((64, 48)))
    report_id = send(intake, body | {"consent": body["consent"] | {"credit": "Aroha"}})
    [photo] = synced(tmp_path, intake)
    assert photo["id"] == f"device-1-{report_id}"
    assert (photo["cohort"], photo["observer"], photo["original_taxon"]) == (
        "device",
        "submitter 1",
        "Ulex europaeus",
    )
    # The capture date as the person saw it, in the device's own offset.
    assert photo["observed_on"] == "2026-10-01"
    assert photo["uploaded_at"] == ReportStore(intake).active()[0].received_at
    assert photo["scores"]["best_species"] == "Ulex europaeus"
    assert photo["scores"]["margin"] == 0.12
    assert (photo["scores"]["width"], photo["scores"]["height"]) == (64, 48)
    assert photo["device"] == {
        "submitter": 1,
        "report_id": report_id,
        "received_at": photo["uploaded_at"],
        "captured_at": "2026-10-01T10:00:00+13:00",
        "app_version": "0.1.0",
        "model_key": "bioclip-2",
        "revision": "f2b4c1d",
        "ranking_revision": 4,
        "score_meaning": "bioclip-2/ranking-4/meaning-1",
        "consent_wording": "2026-11",
        "image_consent": True,
        "location_consent": True,
    }
    # What the person permitted, in the shape the sharing policy reads (#60).
    assert photo["consent"] == {"version": "2026-11", "uses": ["review"], "withdrawn_at": None}
    assert (photo["photo_license"], photo["observation_license"]) == ("cc-by", "cc-by")
    assert photo["attribution"] == "Aroha"


def test_the_exact_device_location_is_kept_with_its_accuracy(tmp_path: Path, intake: Path) -> None:
    send(
        intake, report(location={"latitude": -41.271234, "longitude": 173.283456, "accuracy_m": 8})
    )
    [photo] = synced(tmp_path, intake)
    assert (photo["latitude"], photo["longitude"]) == (-41.271234, 173.283456)
    assert photo["positional_accuracy_m"] == 8
    assert photo["coordinate_status"] == "public"


def test_a_report_without_a_location_or_time_is_not_given_one(tmp_path: Path, intake: Path) -> None:
    unshared = {"wording_version": "2026-11", "image": False, "location": False}
    send(intake, report(location=None, captured_at=None, consent=unshared))
    [photo] = synced(tmp_path, intake)
    assert photo["coordinate_status"] == "missing"
    assert photo["device"]["location_consent"] is False
    assert photo["latitude"] is None and photo["positional_accuracy_m"] is None
    assert photo["observed_on"] is None


def test_the_consented_crop_is_copied_with_its_checksum(tmp_path: Path, intake: Path) -> None:
    send(intake, with_image(jpeg()))
    [photo] = synced(tmp_path, intake)
    path = tmp_path / "pilot" / photo["image_path"]
    assert path.is_relative_to(tmp_path / "pilot" / "images")
    assert hashlib.sha256(path.read_bytes()).hexdigest() == photo["sha256"]
    assert path.stat().st_mode & 0o077 == 0
    assert image_use(photo, "review").action == "show"


def test_no_image_is_kept_or_shown_without_consent(
    tmp_path: Path, intake: Path, client: TestClient
) -> None:
    send(intake, report())
    [photo] = detail(client)["photos"]
    assert photo["image_path"] == "" and photo["device"]["image_consent"] is False
    use = image_use(photo, "review")
    assert use.action == "link" and "did not consent" in use.reason
    response = client.get(f"/runs/{RUN_ID}/photos/{photo['id']}/image")
    assert response.status_code == 403
    assert "did not consent" in response.json()["detail"]


def test_the_review_api_lists_the_device_run_and_serves_its_crop(
    intake: Path, client: TestClient
) -> None:
    send(intake, with_image(jpeg()))
    assert RUN_ID in [run["id"] for run in client.get("/runs").json()]
    [photo] = detail(client)["photos"]
    image = client.get(f"/runs/{RUN_ID}/photos/{photo['id']}/image")
    assert image.status_code == 200 and image.headers["content-type"] == "image/jpeg"


def test_without_an_intake_folder_there_is_no_device_run(tmp_path: Path) -> None:
    client = TestClient(create_app(tmp_path / "pilot"))
    assert client.get(f"/runs/{RUN_ID}").status_code == 404


def test_review_shows_the_exact_point_with_its_accuracy_and_search_area(
    intake: Path, client: TestClient
) -> None:
    send(intake, report())
    [photo] = detail(client)["photos"]
    assert (photo["latitude"], photo["longitude"], photo["positional_accuracy_m"]) == (
        -41.27,
        173.28,
        25,
    )
    area = photo["limits"]["search_area"]
    assert area["status"] == "searchable" and area["radius_m"] == 125


def test_a_withdrawn_report_leaves_the_queue_and_loses_its_image_but_keeps_history(
    tmp_path: Path, intake: Path, client: TestClient
) -> None:
    report_id = send(intake, with_image(jpeg()))
    [photo] = detail(client)["photos"]
    copy = tmp_path / "pilot" / photo["image_path"]
    path = f"/runs/{RUN_ID}/photos/{photo['id']}"
    client.post(f"{path}/review", json={"status": "confirmed", "reviewer": "Ana"})
    judgement = {"dimension": "identity", "value": "confirmed", "reviewer": "Ana"}
    assert client.post(f"{path}/judgements", json=judgement).status_code == 200

    ReportStore(intake).withdraw(1, report_id)

    after = detail(client)
    assert after["photos"] == [] and after["withdrawn_reports"] == 1
    assert after["run"]["detail"] == "0 reports in review · 1 withdrawn"
    assert not copy.exists()
    assert client.get(f"{path}/image").status_code == 404
    # The append-only history stays in the store, without the image or the location;
    # the review API no longer serves any of it (test_device_report_routes.py).
    store = Store(tmp_path / "pilot")
    assert [row["value"] for row in store.judgements(RUN_ID, photo["id"])] == ["confirmed"]
    [kept] = store.photos(RUN_ID)
    assert kept["consent"]["withdrawn_at"] and kept["image_path"] == "" and kept["sha256"] == ""
    assert kept["latitude"] is None and kept["observed_on"] is None
    assert kept["attribution"] == "" and kept["device"]["captured_at"] is None
    assert kept["review_status"] == "confirmed"


def test_a_withdrawn_report_is_not_brought_back(tmp_path: Path, intake: Path) -> None:
    report_id = send(intake, report())
    synced(tmp_path, intake)
    ReportStore(intake).withdraw(1, report_id)
    synced(tmp_path, intake)
    [photo] = synced(tmp_path, intake)
    assert photo["consent"]["withdrawn_at"]


def test_reports_from_one_site_visit_are_grouped(intake: Path, client: TestClient) -> None:
    near = {"latitude": -41.2705, "longitude": 173.28, "accuracy_m": 10}
    send(intake, report())
    send(intake, report(location=near))
    send(intake, report(), submitter=2)
    photos = detail(client)["photos"]
    groups = {photo["observer"]: set() for photo in photos}
    for photo in photos:
        groups[photo["observer"]].add(photo["encounter_group"])
        assert photo["encounter_linkable"]
    assert len(groups["submitter 1"]) == 1 and len(groups["submitter 2"]) == 1
    assert groups["submitter 1"] != groups["submitter 2"]


def test_a_device_report_can_become_a_lead_in_the_follow_up_package(
    intake: Path, client: TestClient
) -> None:
    shared = send(intake, with_image(jpeg(), uses=["review", "agencies"]))
    send(intake, with_image(jpeg()))  # permitted for review only
    lead = {"action": "selected", "selector": "Ana", "reason": "Gorse by the track"}
    for photo in detail(client)["photos"]:
        response = client.post(f"/runs/{RUN_ID}/photos/{photo['id']}/leads", json=lead)
        assert response.status_code == 200, response.text
    leads = client.get(f"/runs/{RUN_ID}/package").json()["leads"]
    images = {item["photo_id"].endswith(shared): item["image"] for item in leads}
    # The crop goes to agencies only where the person permitted it (#60).
    assert images[True]["included"] and images[True]["contributor_permits"] == [
        "agencies",
        "review",
    ]
    assert not images[False]["included"] and "did not permit" in images[False]["terms"]


def test_shared_exports_give_the_point_only_under_the_chosen_licence(
    intake: Path, client: TestClient
) -> None:
    licensed = send(intake, with_image(jpeg()))
    send(intake, report())
    photos = {p["id"]: p for p in client.get(f"/runs/{RUN_ID}/export").json()["photos"]}
    for photo_id, photo in photos.items():
        location = photo["sharing"]["location"]
        if photo_id.endswith(licensed):
            assert (location["latitude"], location["accuracy_m"]) == (-41.27, 25)
        else:
            assert location["latitude"] is None and location["withheld"]
            assert photo["sharing"]["image"]["action"] == "link"


def test_the_review_stack_takes_device_reports_only_when_asked() -> None:
    from weedz.discovery import cli

    assert cli.parse(["dev"]).intake_dir is None
    assert cli.parse(["dev", "--intake-dir", "data/intake"]).intake_dir == Path("data/intake")


def test_a_withdrawn_report_leaves_the_follow_up_package(intake: Path, client: TestClient) -> None:
    report_id = send(intake, with_image(jpeg()))
    [photo] = detail(client)["photos"]
    lead = {"action": "selected", "selector": "Ana", "reason": "Gorse by the track"}
    client.post(f"/runs/{RUN_ID}/photos/{photo['id']}/leads", json=lead)
    ReportStore(intake).withdraw(1, report_id)
    assert client.get(f"/runs/{RUN_ID}/package").json()["leads"] == []
