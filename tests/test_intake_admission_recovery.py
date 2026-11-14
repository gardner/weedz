"""An interrupted admission is reusable only by the same report content (#97)."""

import hashlib
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from intake_helpers import new_id, report
from test_intake_concurrency import token

from weedz.intake.api import create_intake_app
from weedz.intake.limits import Limits
from weedz.intake.schema import Report
from weedz.intake.store import ReportStore


def test_an_interrupted_admission_retries_at_the_daily_limit(tmp_path: Path) -> None:
    limits, report_id = Limits(reports_per_day=1), new_id()
    secret = token(tmp_path)
    content = Report.model_validate_json(json.dumps(report()))
    digest = hashlib.sha256(content.model_dump_json().encode()).hexdigest()
    store = ReportStore(tmp_path)
    assert store.admit(1, report_id, digest, False, limits) is None
    # No receive(): the previous process stopped between admission and storage.
    client = TestClient(create_intake_app(tmp_path, limits))
    headers = {"Authorization": f"Bearer {secret}"}
    changed = report(app_version="0.2.0")
    assert client.put(f"/reports/{report_id}", json=changed, headers=headers).status_code == 409
    assert client.put(f"/reports/{report_id}", json=report(), headers=headers).status_code == 201
    assert client.put(f"/reports/{new_id()}", json=report(), headers=headers).status_code == 429


def test_a_completed_decode_refusal_cannot_reuse_an_admission(tmp_path: Path) -> None:
    from intake_helpers import with_image

    client = TestClient(create_intake_app(tmp_path, Limits(reports_per_day=1)))
    headers = {"Authorization": f"Bearer {token(tmp_path)}"}
    path, body = f"/reports/{new_id()}", with_image(b"not an image")
    assert client.put(path, json=body, headers=headers).status_code == 422
    assert client.put(path, json=body, headers=headers).status_code == 429


def test_expired_admissions_do_not_keep_old_content_digests(tmp_path: Path) -> None:
    import sqlite3
    from datetime import UTC, datetime, timedelta

    limits, report_id = Limits(reports_per_day=1), new_id()
    secret, store = token(tmp_path), ReportStore(tmp_path)
    store.admit(1, report_id, "old-digest", False, limits)
    with sqlite3.connect(store.path) as db:
        day_ago = (datetime.now(UTC) - timedelta(days=1, seconds=1)).isoformat()
        db.execute("UPDATE usage SET used_at=?", (day_ago,))
    client = TestClient(create_intake_app(tmp_path, limits))
    response = client.put(
        f"/reports/{report_id}", json=report(), headers={"Authorization": f"Bearer {secret}"}
    )
    assert response.status_code == 201
    with sqlite3.connect(store.path) as db:
        assert db.execute("SELECT COUNT(*) FROM admissions").fetchone() == (0,)


def test_pending_upload_can_be_withdrawn_even_at_its_daily_limit(tmp_path: Path) -> None:
    limits, report_id = Limits(reports_per_day=1), new_id()
    secret, store = token(tmp_path), ReportStore(tmp_path)
    store.admit(1, report_id, "pending-digest", False, limits)
    client = TestClient(create_intake_app(tmp_path, limits))
    headers = {"Authorization": f"Bearer {secret}"}
    assert client.delete(f"/reports/{report_id}", headers=headers).status_code == 200
    assert client.put(f"/reports/{report_id}", json=report(), headers=headers).status_code == 410


def test_a_completed_image_budget_refusal_cannot_decode_for_free(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from intake_helpers import jpeg, with_image

    from weedz.intake.images import clean_image

    decoded: list[int] = []

    def count(data: bytes, max_pixels: int) -> bytes:
        decoded.append(1)
        return clean_image(data, max_pixels)

    monkeypatch.setattr("weedz.intake.api.clean_image", count)

    def unavailable(store: ReportStore, submitter: int, report_id: str) -> None:
        raise OSError("A second cleanup write cannot acquire the database")

    monkeypatch.setattr(ReportStore, "refused_admission", unavailable)
    client = TestClient(
        create_intake_app(tmp_path, Limits(reports_per_day=1, image_bytes_per_day=1)),
        raise_server_exceptions=False,
    )
    headers = {"Authorization": f"Bearer {token(tmp_path)}"}
    path, body = f"/reports/{new_id()}", with_image(jpeg())
    assert client.put(path, json=body, headers=headers).status_code == 429
    assert decoded == [1]
    assert client.put(path, json=body, headers=headers).status_code == 429
    assert decoded == [1], "A completed refusal must spend its report charge"
    assert client.put(path, json=report(), headers=headers).status_code == 429


def test_reservation_expiring_during_decoding_is_charged_again_before_storage(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import sqlite3
    from datetime import UTC, datetime, timedelta

    from intake_helpers import jpeg, with_image

    from weedz.intake import budget
    from weedz.intake.images import clean_image

    now = datetime.now(UTC)
    clock = [now]
    monkeypatch.setattr(budget, "_now", lambda: clock[0])
    limits, report_id = Limits(reports_per_day=1), new_id()
    secret, store = token(tmp_path), ReportStore(tmp_path)
    body = with_image(jpeg())
    parsed = Report.model_validate_json(json.dumps(body))
    digest = hashlib.sha256(parsed.model_dump_json().encode()).hexdigest()
    store.admit(1, report_id, digest, True, limits)
    with sqlite3.connect(store.path) as db:
        almost_a_day = now - timedelta(days=1) + timedelta(seconds=1)
        db.execute("UPDATE usage SET used_at=?", (budget.stamp(almost_a_day),))

    def cross_expiry(data: bytes, max_pixels: int) -> bytes:
        clock[0] = now + timedelta(seconds=2)
        return clean_image(data, max_pixels)

    monkeypatch.setattr("weedz.intake.api.clean_image", cross_expiry)
    client = TestClient(create_intake_app(tmp_path, limits))
    headers = {"Authorization": f"Bearer {secret}"}
    assert client.put(f"/reports/{report_id}", json=body, headers=headers).status_code == 201
    with sqlite3.connect(store.path) as db:
        rows = db.execute("SELECT image_bytes FROM usage").fetchall()
        assert len(rows) == 1 and rows[0][0] > 0
    assert client.put(f"/reports/{new_id()}", json=report(), headers=headers).status_code == 429
