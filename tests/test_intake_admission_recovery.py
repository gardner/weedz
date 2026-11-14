"""An interrupted admission is reusable only by the same report content (#97)."""

import hashlib
import json
from pathlib import Path

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
