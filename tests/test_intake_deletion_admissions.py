"""Bulk deletion erases temporary upload hashes as well as committed content (#97/#101)."""

import hashlib
import json
import sqlite3
from pathlib import Path

from fastapi.testclient import TestClient
from intake_helpers import new_id, report
from test_intake_concurrency import token

from weedz.intake.api import create_intake_app
from weedz.intake.limits import Limits
from weedz.intake.schema import Report
from weedz.intake.store import ReportStore


def test_bulk_erasure_removes_only_its_submitters_pending_admission(tmp_path: Path) -> None:
    secret = token(tmp_path)
    token(tmp_path)  # another device's uncompleted upload must remain untouched
    client = TestClient(create_intake_app(tmp_path))
    store, limits = ReportStore(tmp_path), Limits()
    parsed = Report.model_validate_json(json.dumps(report()))
    digest = hashlib.sha256(parsed.model_dump_json().encode()).hexdigest()
    store.admit(1, new_id(), digest, False, limits)
    other_id = new_id()
    store.admit(2, other_id, "another-device-digest", False, limits)
    store._mark_withdrawal(1, new_id(), True, limits)
    other_pending = new_id()
    store._mark_withdrawal(2, other_pending, True, limits)
    response = client.delete("/submitter", headers={"Authorization": f"Bearer {secret}"})
    assert response.status_code == 200
    assert response.json()["status"] == "deleted"
    with sqlite3.connect(store.path) as db:
        rows = db.execute("SELECT submitter,report_id,content_sha256 FROM admissions").fetchall()
        assert rows == [(2, other_id, "another-device-digest")]
        pending = db.execute("SELECT * FROM pending_report_erasures").fetchall()
        assert pending == [(2, other_pending)]
    assert digest.encode() not in store.path.read_bytes()
