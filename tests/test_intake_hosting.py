"""Bound slow requests and database contention without losing retryability (#97)."""

import asyncio
import json
import sqlite3
from pathlib import Path

from fastapi.testclient import TestClient
from intake_helpers import new_id, report
from test_intake_concurrency import call, token

from weedz.intake.api import create_intake_app
from weedz.intake.limits import Limits
from weedz.intake.store import ReportStore


def test_a_steady_body_still_has_a_total_deadline(tmp_path: Path) -> None:
    app = create_intake_app(tmp_path, Limits(body_idle_seconds=0.2, body_total_seconds=0.25))
    body = json.dumps(report()).encode()
    parts = [body[:20], 0.15, body[20:40], 0.15, body[40:]]
    path = f"/reports/{new_id()}"
    assert asyncio.run(call(app, "PUT", path, token(tmp_path), parts)) == 408
    assert ReportStore(tmp_path).active() == []


def test_database_contention_returns_a_retryable_response(tmp_path: Path) -> None:
    limits = Limits(sqlite_busy_seconds=0.01)
    app = create_intake_app(tmp_path, limits)
    headers = {"Authorization": f"Bearer {token(tmp_path)}"}
    store = ReportStore(tmp_path)
    with sqlite3.connect(store.path) as held:
        held.execute("BEGIN IMMEDIATE")
        response = TestClient(app).put(f"/reports/{new_id()}", json=report(), headers=headers)
        assert response.status_code == 503
        assert response.headers["Retry-After"] == "1"
    assert store.active() == []


def test_auth_database_contention_returns_a_retryable_response(tmp_path: Path) -> None:
    app = create_intake_app(tmp_path, Limits(sqlite_busy_seconds=0.01))
    headers = {"Authorization": f"Bearer {token(tmp_path)}"}
    with sqlite3.connect(tmp_path / "submitters.sqlite3") as held:
        held.execute("BEGIN EXCLUSIVE")
        response = TestClient(app).get(f"/reports/{new_id()}", headers=headers)
        assert response.status_code == 503
        assert response.headers["Retry-After"] == "1"
