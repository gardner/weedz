"""Image work is bounded even if recording a later refusal cannot acquire SQLite (#97)."""

import hashlib
import json
import sqlite3
from contextlib import closing
from datetime import UTC, datetime, timedelta
from io import BytesIO
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from intake_helpers import jpeg, new_id, with_image
from PIL import Image
from test_intake_concurrency import token

from weedz.intake import budget
from weedz.intake.api import create_intake_app
from weedz.intake.images import clean_image
from weedz.intake.limits import Limits
from weedz.intake.schema import Report
from weedz.intake.store import ReportStore, Withdrawn


def test_cleanup_contention_cannot_allow_unbounded_image_work(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    out = BytesIO()
    Image.new("RGB", (10, 10)).save(out, "PNG")
    upload = out.getvalue()  # its cleaned JPEG exceeds this small PNG's byte length
    limits = Limits(
        reports_per_day=1,
        image_attempts_per_day=2,
        max_image_bytes=len(upload) + 1,
        sqlite_busy_seconds=0.01,
    )
    client = TestClient(create_intake_app(tmp_path, limits))
    headers = {"Authorization": f"Bearer {token(tmp_path)}"}
    path, body = f"/reports/{new_id()}", with_image(upload)
    decoded: list[int] = []
    original = ReportStore.refused_admission

    def count(data: bytes, max_pixels: int) -> bytes:
        decoded.append(1)
        return clean_image(data, max_pixels)

    def contention(store: ReportStore, submitter: int, report_id: str) -> None:
        with closing(sqlite3.connect(store.path)) as held, held:
            held.execute("BEGIN IMMEDIATE")
            original(store, submitter, report_id)

    monkeypatch.setattr("weedz.intake.api.clean_image", count)
    monkeypatch.setattr(ReportStore, "refused_admission", contention)
    for _ in range(2):
        assert client.put(path, json=body, headers=headers).status_code == 503
    response = client.put(path, json=body, headers=headers)
    assert response.status_code == 429
    assert int(response.headers["Retry-After"]) > 0
    assert decoded == [1, 1]


def test_attempt_charge_contention_performs_no_image_work(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    client = TestClient(create_intake_app(tmp_path, Limits(sqlite_busy_seconds=0.01)))
    headers = {"Authorization": f"Bearer {token(tmp_path)}"}
    original = ReportStore.charge_image_attempt

    def contention(store: ReportStore, submitter: int, report_id: str, limits: Limits) -> None:
        with closing(sqlite3.connect(store.path)) as held, held:
            held.execute("BEGIN IMMEDIATE")
            original(store, submitter, report_id, limits)

    def never(*args: object) -> bytes:
        pytest.fail("A failed work charge must happen before decoding")

    monkeypatch.setattr(ReportStore, "charge_image_attempt", contention)
    monkeypatch.setattr("weedz.intake.api.clean_image", never)
    response = client.put(f"/reports/{new_id()}", json=with_image(jpeg()), headers=headers)
    assert response.status_code == 503


def test_interrupted_image_retry_reuses_report_charge_but_spends_an_attempt(tmp_path: Path) -> None:
    limits = Limits(reports_per_day=1, image_attempts_per_day=2)
    secret, report_id = token(tmp_path), new_id()
    body = with_image(jpeg())
    parsed = Report.model_validate_json(json.dumps(body))
    digest = hashlib.sha256(parsed.model_dump_json().encode()).hexdigest()
    store = ReportStore(tmp_path)
    store.admit(1, report_id, digest, True, limits)
    store.charge_image_attempt(1, report_id, limits)
    # The preceding worker stopped before storage; retry at the report-count limit.
    client = TestClient(create_intake_app(tmp_path, limits))
    headers, path = {"Authorization": f"Bearer {secret}"}, f"/reports/{report_id}"
    assert client.put(path, json=body, headers=headers).status_code == 201
    assert client.put(path, json=body, headers=headers).status_code == 200
    with sqlite3.connect(store.path) as db:
        assert db.execute("SELECT COUNT(*) FROM usage").fetchone() == (1,)
        assert db.execute("SELECT COUNT(*) FROM image_attempts").fetchone() == (2,)


def test_work_allowance_expires_and_reports_when_an_attempt_becomes_available(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    now = datetime.now(UTC)
    clock = [now]
    monkeypatch.setattr(budget, "_now", lambda: clock[0])
    store, limits = ReportStore(tmp_path), Limits(image_attempts_per_day=1)
    report_id = new_id()
    store.charge_image_attempt(1, report_id, limits)
    clock[0] = now + timedelta(hours=1)
    with pytest.raises(budget.OverBudget) as refused:
        store.charge_image_attempt(1, report_id, limits)
    assert refused.value.retry_after == 23 * 3600 + 1
    clock[0] = now + timedelta(days=1, seconds=1)
    store.charge_image_attempt(1, report_id, limits)
    with sqlite3.connect(store.path) as db:
        assert db.execute("SELECT COUNT(*) FROM image_attempts").fetchone() == (1,)


def test_image_work_cannot_be_charged_after_a_bulk_deletion_barrier(tmp_path: Path) -> None:
    from weedz.intake.deletion import Deletions

    token(tmp_path)
    Deletions(tmp_path).begin(1)
    store = ReportStore(tmp_path)
    with pytest.raises(Withdrawn):
        store.charge_image_attempt(1, new_id(), Limits())
    with sqlite3.connect(store.path) as db:
        assert db.execute("SELECT COUNT(*) FROM image_attempts").fetchone() == (0,)
