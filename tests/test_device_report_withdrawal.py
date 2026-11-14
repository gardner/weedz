"""A withdrawal erases a device report from review, and nothing else does (issue #58)."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from intake_helpers import jpeg, report, with_image
from test_device_reports import send, synced

from weedz.discovery import device_reports
from weedz.discovery.api import create_app
from weedz.discovery.device_reports import RUN_ID
from weedz.discovery.store import Store
from weedz.intake.store import ReportStore


def credited(location: dict) -> dict:
    body = with_image(jpeg(), location=location)
    return body | {"consent": body["consent"] | {"credit": "Aroha Unique"}}


def test_a_report_missing_from_intake_is_not_erased(tmp_path: Path) -> None:
    """A wrong or empty intake folder is not a withdrawal."""
    intake = tmp_path / "intake"
    send(intake, with_image(jpeg()))
    [before] = synced(tmp_path, intake)
    [after] = synced(tmp_path, tmp_path / "elsewhere")
    assert not after.get("withdrawn_at") and after["latitude"] == -41.27
    assert (tmp_path / "pilot" / after["image_path"]).is_file()
    assert synced(tmp_path, intake) == [after] and after["id"] == before["id"]


def test_a_withdrawal_leaves_no_trace_in_the_database_files(tmp_path: Path) -> None:
    intake = tmp_path / "intake"
    point = {"latitude": -41.271234, "longitude": 173.283456, "accuracy_m": 8}
    report_id = send(intake, credited(location=point))
    synced(tmp_path, intake)
    ReportStore(intake).withdraw(1, report_id)
    synced(tmp_path, intake)
    files = sorted((tmp_path / "pilot").glob("discovery.sqlite3*"))
    raw = b"".join(path.read_bytes() for path in files)
    for detail in (b"Aroha Unique", b"-41.271234", b"173.283456", b"2026-10-01T10:00:00"):
        assert detail not in raw


def test_the_review_database_is_owner_only_once_it_holds_device_reports(tmp_path: Path) -> None:
    intake = tmp_path / "intake"
    send(intake, report())
    synced(tmp_path, intake)
    for path in (tmp_path / "pilot").glob("discovery.sqlite3*"):
        assert path.stat().st_mode & 0o077 == 0, path.name


def test_a_crop_written_while_its_report_is_withdrawn_is_deleted(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    intake = tmp_path / "intake"
    report_id = send(intake, with_image(jpeg()))
    write = device_reports._write_private

    def withdrawn_meanwhile(target: Path, data: bytes) -> None:
        ReportStore(intake).withdraw(1, report_id)
        device_reports.sync(Store(tmp_path / "pilot"), ReportStore(intake))
        write(target, data)

    monkeypatch.setattr(device_reports, "_write_private", withdrawn_meanwhile)
    [photo] = synced(tmp_path, intake)
    assert photo["withdrawn_at"]
    assert list((tmp_path / "pilot" / "images" / "device").iterdir()) == []


def test_a_consented_crop_that_is_gone_is_not_offered(tmp_path: Path) -> None:
    intake = tmp_path / "intake"
    send(intake, with_image(jpeg()))
    [stored] = ReportStore(intake).active()
    assert stored.image is not None
    stored.image.unlink()
    [photo] = synced(tmp_path, intake)
    assert photo["image_path"] == "" and photo["device"]["image_consent"] is True


def test_a_referral_on_a_withdrawn_report_cannot_be_answered(tmp_path: Path) -> None:
    intake = tmp_path / "intake"
    client = TestClient(create_app(tmp_path / "pilot", intake_dir=intake))
    report_id = send(intake, report())
    [photo] = client.get(f"/runs/{RUN_ID}").json()["photos"]
    path = f"/runs/{RUN_ID}/photos/{photo['id']}/referrals"
    referral = {"reason": "lookalike", "note": "Check", "referrer": "Ana"}
    referral_id = client.post(path, json=referral).json()["id"]
    ReportStore(intake).withdraw(1, report_id)
    answer = {"action": "answered", "actor": "Dr Wiri", "note": "Native"}
    response = client.post(f"{path}/{referral_id}/events", json=answer)
    assert response.status_code == 410, response.text
