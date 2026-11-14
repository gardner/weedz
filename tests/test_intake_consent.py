"""The intake records what each person agreed to, and keeps that record past withdrawal (#60)."""

import sqlite3
from pathlib import Path

from fastapi.testclient import TestClient
from intake_helpers import jpeg, new_id, report, with_image

from weedz.intake.api import create_intake_app
from weedz.intake.rights import photo_rights
from weedz.intake.store import ReportStore
from weedz.intake.submitters import Submitters


def setup(tmp_path: Path) -> tuple[TestClient, dict[str, str]]:
    token = Submitters(tmp_path).issue("Pilot phone").token
    return TestClient(create_intake_app(tmp_path)), {"Authorization": f"Bearer {token}"}


def test_a_report_under_an_unpublished_wording_is_refused(tmp_path: Path) -> None:
    client, headers = setup(tmp_path)
    body = report(consent={"wording_version": "2099-01", "image": False})
    assert client.put(f"/reports/{new_id()}", json=body, headers=headers).status_code == 422


def test_a_report_with_an_unsupported_licence_is_refused(tmp_path: Path) -> None:
    client, headers = setup(tmp_path)
    body = with_image(jpeg(), licence="cc-by-sa")
    assert client.put(f"/reports/{new_id()}", json=body, headers=headers).status_code == 422


def test_the_receipt_shows_the_wording_and_uses_agreed(tmp_path: Path) -> None:
    client, headers = setup(tmp_path)
    body = with_image(jpeg(), uses=["training", "review"])
    receipt = client.put(f"/reports/{new_id()}", json=body, headers=headers).json()
    assert receipt["consent_version"] == "2026-11"
    assert receipt["uses"] == ["review", "training"]


def test_stored_reports_give_their_photo_rights(tmp_path: Path) -> None:
    client, headers = setup(tmp_path)
    body = with_image(jpeg(), uses=["review", "agencies"], credit="Ana Smith")
    client.put(f"/reports/{new_id()}", json=body, headers=headers)
    (stored,) = ReportStore(tmp_path).active()
    rights = photo_rights(stored.report.consent)
    assert rights is not None and rights.consent is not None
    assert rights.consent.uses == frozenset({"review", "agencies"})
    assert rights.attribution == "Photo: Ana Smith via Weedz, CC BY 4.0"


def test_withdrawal_keeps_what_was_agreed_but_no_credit_name(tmp_path: Path) -> None:
    client, headers = setup(tmp_path)
    path = f"/reports/{new_id()}"
    body = with_image(jpeg(), uses=["review", "training"], credit="Ana Smith")
    client.put(path, json=body, headers=headers)
    withdrawn = client.delete(path, headers=headers).json()
    assert withdrawn["status"] == "withdrawn"
    assert withdrawn["consent_version"] == "2026-11"
    assert withdrawn["uses"] == ["review", "training"]
    assert client.get(path, headers=headers).json()["uses"] == ["review", "training"]
    assert b"Ana Smith" not in (tmp_path / "reports" / "reports.sqlite3").read_bytes()
    with sqlite3.connect(tmp_path / "reports" / "reports.sqlite3") as db:
        (credit,) = db.execute("SELECT consent FROM reports").fetchone()
    assert "Ana" not in credit


def test_a_store_from_before_consent_records_gains_them(tmp_path: Path) -> None:
    folder = tmp_path / "reports"
    folder.mkdir()
    with sqlite3.connect(folder / "reports.sqlite3") as db:
        db.execute(
            "CREATE TABLE reports(submitter INTEGER NOT NULL, report_id TEXT NOT NULL, "
            "received_at TEXT NOT NULL, content_sha256 TEXT, body TEXT, image_file TEXT, "
            "withdrawn_at TEXT, PRIMARY KEY(submitter, report_id))"
        )
        db.execute("INSERT INTO reports VALUES(1, 'old', 't', NULL, NULL, NULL, 't')")
    client, headers = setup(tmp_path)
    assert client.put(f"/reports/{new_id()}", json=report(), headers=headers).status_code == 201
    old = ReportStore(tmp_path).receipt(1, "old")
    assert old is not None
    assert (old.consent_version, old.uses) == (None, [])
