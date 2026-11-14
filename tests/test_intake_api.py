"""Device report intake (issue #57): who may send, what is accepted, and what is kept."""

import json
import logging
import os
import sqlite3
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from io import BytesIO
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from intake_helpers import jpeg, new_id, report, with_image
from PIL import Image

from weedz.discovery.access import Access
from weedz.intake.api import create_intake_app
from weedz.intake.limits import Limits
from weedz.intake.store import ReportStore
from weedz.intake.submitters import Submitters


@pytest.fixture
def client(tmp_path: Path) -> TestClient:
    return TestClient(create_intake_app(tmp_path))


def auth(tmp_path: Path, label: str = "Pilot phone 1") -> dict[str, str]:
    return {"Authorization": f"Bearer {Submitters(tmp_path).issue(label).token}"}


def images(tmp_path: Path) -> list[Path]:
    folder = tmp_path / "reports" / "images"
    return sorted(folder.iterdir()) if folder.exists() else []


def test_every_report_route_needs_a_submitter_token(client: TestClient) -> None:
    path = f"/reports/{new_id()}"
    for response in (client.put(path, json=report()), client.get(path), client.delete(path)):
        assert response.status_code == 401
        assert response.headers["WWW-Authenticate"] == "Bearer"


def test_revoked_reviewer_and_query_tokens_are_refused(tmp_path: Path, client: TestClient) -> None:
    submitters = Submitters(tmp_path)
    revoked = submitters.issue("Old phone")
    assert submitters.revoke(revoked.id)
    reviewer = Access(tmp_path).invite("Ana").token
    path = f"/reports/{new_id()}"
    for token in (revoked.token, reviewer, "weedzsub_1_guess", "garbage"):
        response = client.put(path, json=report(), headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 401
    live = submitters.issue("New phone").token
    assert client.put(f"{path}?token={live}", json=report()).status_code == 401


def test_a_report_is_received_once_and_retries_get_the_same_receipt(
    tmp_path: Path, client: TestClient
) -> None:
    headers, path = auth(tmp_path), f"/reports/{new_id()}"
    first = client.put(path, json=report(), headers=headers)
    assert first.status_code == 201
    receipt = first.json()
    assert receipt["status"] == "received" and receipt["image"] is False
    retry = client.put(path, json=report(), headers=headers)
    assert retry.status_code == 200 and retry.json() == receipt
    assert client.get(path, headers=headers).json() == receipt
    assert len(ReportStore(tmp_path).active()) == 1


def test_different_content_under_a_used_report_id_is_a_conflict(
    tmp_path: Path, client: TestClient
) -> None:
    headers, path = auth(tmp_path), f"/reports/{new_id()}"
    client.put(path, json=report(), headers=headers)
    changed = report(candidate={"taxon": "Cortaderia selloana", "score": 0.3})
    assert client.put(path, json=changed, headers=headers).status_code == 409


@pytest.mark.parametrize(
    "body",
    [
        report(extra="field"),
        report(schema_version=2),
        report(candidate={"taxon": "Not a target", "score": 0.1}),
        report(location={"latitude": -41.27, "longitude": 173.28}),
        report(location={"latitude": -91, "longitude": 173.28, "accuracy_m": 5}),
        report(captured_at="2026-10-01T10:00:00"),
        report(consent={"wording_version": "2026-11", "image": False, "licence": "cc-by-nd"}),
        report(app_version="x" * 500),
    ],
)
def test_malformed_reports_are_refused(tmp_path: Path, client: TestClient, body: dict) -> None:
    response = client.put(f"/reports/{new_id()}", json=body, headers=auth(tmp_path))
    assert response.status_code == 422
    assert ReportStore(tmp_path).active() == []


def test_non_json_bodies_and_bad_ids_are_refused(tmp_path: Path, client: TestClient) -> None:
    headers = auth(tmp_path)
    path = f"/reports/{new_id()}"
    nan = json.dumps(report()).replace("0.12", "NaN")
    json_headers = headers | {"Content-Type": "application/json"}
    assert client.put(path, content=nan, headers=json_headers).status_code == 422
    assert client.put(path, content="{", headers=json_headers).status_code == 422
    text_headers = headers | {"Content-Type": "text/plain"}
    assert client.put(path, content=json.dumps(report()), headers=text_headers).status_code == 415
    assert client.put("/reports/not-a-uuid", json=report(), headers=headers).status_code == 422


def test_oversize_bodies_are_refused_with_or_without_a_length(tmp_path: Path) -> None:
    client = TestClient(create_intake_app(tmp_path, Limits(max_body_bytes=1000)))
    headers = auth(tmp_path) | {"Content-Type": "application/json"}
    big = json.dumps(report(app_version="1")) + " " * 2000

    def chunks() -> Iterator[bytes]:
        yield big.encode()

    assert client.put(f"/reports/{new_id()}", content=big, headers=headers).status_code == 413
    assert client.put(f"/reports/{new_id()}", content=chunks(), headers=headers).status_code == 413
    assert ReportStore(tmp_path).active() == []


def test_an_image_without_consent_and_licence_is_refused_and_not_stored(
    tmp_path: Path, client: TestClient
) -> None:
    headers = auth(tmp_path)
    unconsented = with_image(jpeg()) | {"consent": {"wording_version": "2026-11", "image": False}}
    unlicensed = with_image(jpeg()) | {"consent": {"wording_version": "2026-11", "image": True}}
    for body in (unconsented, unlicensed):
        path = f"/reports/{new_id()}"
        assert client.put(path, json=body, headers=headers).status_code == 422
        assert client.get(path, headers=headers).status_code == 404
    assert images(tmp_path) == []
    assert ReportStore(tmp_path).active() == []


def test_image_consent_without_an_image_is_refused(tmp_path: Path, client: TestClient) -> None:
    body = report(consent={"wording_version": "2026-11", "image": True, "licence": "cc0"})
    assert client.put(f"/reports/{new_id()}", json=body, headers=auth(tmp_path)).status_code == 422


def test_undecodable_or_oversize_images_are_refused(tmp_path: Path) -> None:
    client = TestClient(create_intake_app(tmp_path, Limits(max_pixels=100 * 100)))
    headers = auth(tmp_path)
    bad = with_image(b"not an image")
    bad_base64 = with_image(jpeg()) | {"image": "***"}
    huge = with_image(jpeg((200, 200)))
    for body in (bad, bad_base64, huge):
        assert client.put(f"/reports/{new_id()}", json=body, headers=headers).status_code == 422
    assert images(tmp_path) == []


def test_withdrawal_deletes_the_image_and_erases_the_report(
    tmp_path: Path, client: TestClient
) -> None:
    headers, path = auth(tmp_path), f"/reports/{new_id()}"
    body = with_image(jpeg())
    assert client.put(path, json=body, headers=headers).json()["image"] is True
    assert len(images(tmp_path)) == 1
    withdrawn = client.delete(path, headers=headers)
    assert withdrawn.status_code == 200
    assert withdrawn.json()["status"] == "withdrawn" and withdrawn.json()["withdrawn_at"]
    assert images(tmp_path) == []
    assert ReportStore(tmp_path).active() == []
    assert client.get(path, headers=headers).json()["status"] == "withdrawn"
    assert client.delete(path, headers=headers).status_code == 200
    assert client.put(path, json=body, headers=headers).status_code == 410
    stored = (tmp_path / "reports" / "reports.sqlite3").read_bytes()
    assert b"Ulex" not in stored and b"173.28" not in stored


def test_one_submitter_cannot_read_or_withdraw_anothers_report(
    tmp_path: Path, client: TestClient
) -> None:
    owner, other = auth(tmp_path, "Phone A"), auth(tmp_path, "Phone B")
    path = f"/reports/{new_id()}"
    client.put(path, json=with_image(jpeg()), headers=owner)
    assert client.get(path, headers=other).status_code == 404
    assert client.delete(path, headers=other).status_code == 404
    assert len(images(tmp_path)) == 1
    assert client.get(path, headers=owner).json()["status"] == "received"


def test_tokens_are_never_logged_or_echoed(
    tmp_path: Path, client: TestClient, caplog: pytest.LogCaptureFixture
) -> None:
    submitters = Submitters(tmp_path)
    credential = submitters.issue("Phone")
    revoked = submitters.issue("Old")
    submitters.revoke(revoked.id)
    caplog.set_level(logging.DEBUG)
    bodies = []
    for token in (credential.token, revoked.token):
        headers = {"Authorization": f"Bearer {token}"}
        path = f"/reports/{new_id()}"
        bodies += [client.put(path, json=report(), headers=headers).text]
        bodies += [client.get(path, headers=headers).text]
        bodies += [client.delete(path, headers=headers).text]
    for token in (credential.token, revoked.token):
        secret = token.rsplit("_", 1)[-1]
        assert secret not in caplog.text
        assert all(secret not in body for body in bodies)
        assert secret not in repr(credential)
    assert secret not in json.dumps(submitters.listing())


def test_each_submitter_has_a_daily_budget_that_withdrawal_does_not_reset(tmp_path: Path) -> None:
    client = TestClient(create_intake_app(tmp_path, Limits(reports_per_day=2)))
    headers = auth(tmp_path)
    first = f"/reports/{new_id()}"
    client.put(first, json=report(), headers=headers)
    client.delete(first, headers=headers)
    second = f"/reports/{new_id()}"
    assert client.put(second, json=report(), headers=headers).status_code == 201
    refused = client.put(f"/reports/{new_id()}", json=report(), headers=headers)
    assert refused.status_code == 429 and int(refused.headers["Retry-After"]) > 0
    # A retry of a report already received is not new work, so the budget does not refuse it.
    assert client.put(second, json=report(), headers=headers).status_code == 200
    other = auth(tmp_path, "Another phone")
    assert client.put(f"/reports/{new_id()}", json=report(), headers=other).status_code == 201


def test_image_bytes_count_against_the_daily_budget(tmp_path: Path) -> None:
    client = TestClient(create_intake_app(tmp_path, Limits(image_bytes_per_day=1)))
    response = client.put(f"/reports/{new_id()}", json=with_image(jpeg()), headers=auth(tmp_path))
    assert response.status_code == 429
    assert images(tmp_path) == []


def test_reports_are_kept_apart_owner_only_and_offered_for_review_unpublished(
    tmp_path: Path, client: TestClient
) -> None:
    report_id = new_id()
    client.put(f"/reports/{report_id}", json=with_image(jpeg()), headers=auth(tmp_path))
    [stored] = ReportStore(tmp_path).active()
    assert stored.report_id == report_id and stored.report.candidate.taxon == "Ulex europaeus"
    assert stored.image is not None and stored.image.read_bytes()[:2] == b"\xff\xd8"
    folder = tmp_path / "reports"
    for path in (folder, folder / "images", folder / "reports.sqlite3", stored.image):
        assert path.stat().st_mode & 0o077 == 0
    assert not (tmp_path / "discovery.sqlite3").exists()
    assert client.get("/openapi.json").status_code in {401, 404}


def test_overlong_token_ids_are_refused_not_errors(tmp_path: Path, client: TestClient) -> None:
    for token in ("weedzsub_" + "9" * 30 + "_x", "weedz_" + "9" * 30 + "_x"):
        headers = {"Authorization": f"Bearer {token}"}
        assert client.get(f"/reports/{new_id()}", headers=headers).status_code == 401
    assert Access(tmp_path).reviewer("weedz_" + "9" * 30 + "_x") is None


def test_a_report_over_budget_is_refused_before_its_image_is_decoded(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def never(*_args: object) -> bytes:
        raise AssertionError("decoded an image that the budget refuses")

    monkeypatch.setattr("weedz.intake.api.clean_image", never)
    client = TestClient(create_intake_app(tmp_path, Limits(reports_per_day=0)))
    response = client.put(f"/reports/{new_id()}", json=with_image(jpeg()), headers=auth(tmp_path))
    assert response.status_code == 429


def test_a_crop_that_grows_past_the_limit_when_re_encoded_is_refused(tmp_path: Path) -> None:
    noise = Image.frombytes("RGB", (300, 300), os.urandom(300 * 300 * 3))
    out = BytesIO()
    noise.save(out, "WEBP", quality=1)
    upload = out.getvalue()
    client = TestClient(create_intake_app(tmp_path, Limits(max_image_bytes=len(upload) + 1)))
    response = client.put(f"/reports/{new_id()}", json=with_image(upload), headers=auth(tmp_path))
    assert response.status_code == 413
    assert images(tmp_path) == []


def test_retry_after_waits_until_enough_image_bytes_expire(tmp_path: Path) -> None:
    """The oldest report has no image, so its expiry alone frees no image bytes."""
    headers = auth(tmp_path)
    client = TestClient(create_intake_app(tmp_path, Limits(image_bytes_per_day=len(jpeg()) * 3)))
    client.put(f"/reports/{new_id()}", json=report(), headers=headers)
    client.put(f"/reports/{new_id()}", json=with_image(jpeg()), headers=headers)
    now = datetime.now(UTC)
    with sqlite3.connect(tmp_path / "reports" / "reports.sqlite3") as db:
        db.execute(
            "UPDATE reports SET received_at=? WHERE image_bytes=0",
            ((now - timedelta(hours=23)).isoformat(timespec="microseconds"),),
        )
        db.execute(
            "UPDATE reports SET received_at=?, image_bytes=? WHERE image_bytes>0",
            ((now - timedelta(hours=1)).isoformat(timespec="microseconds"), len(jpeg()) * 3),
        )
    refused = client.put(f"/reports/{new_id()}", json=with_image(jpeg()), headers=headers)
    assert refused.status_code == 429
    assert int(refused.headers["Retry-After"]) > 22 * 3600
