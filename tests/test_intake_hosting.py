"""Bound slow requests and database contention without losing retryability (#97)."""

import asyncio
import json
import sqlite3
import threading
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from intake_helpers import jpeg, new_id, report, with_image
from test_intake_concurrency import call, token

from weedz.intake.api import create_intake_app
from weedz.intake.limits import Limits
from weedz.intake.store import ReportStore
from weedz.intake.turns import SubmitterTurns, TurnBusy


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


def test_cancelling_upload_keeps_its_turn_until_the_worker_finishes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    decoding, release = threading.Event(), threading.Event()

    def slow(data: bytes, max_pixels: int) -> bytes:
        decoding.set()
        assert release.wait(5)
        return jpeg()

    monkeypatch.setattr("weedz.intake.api.clean_image", slow)
    app = create_intake_app(tmp_path)
    secret = token(tmp_path)

    async def scenario() -> None:
        upload = asyncio.create_task(
            call(
                app,
                "PUT",
                f"/reports/{new_id()}",
                secret,
                [json.dumps(with_image(jpeg())).encode()],
            )
        )
        try:
            while not decoding.is_set():
                await asyncio.sleep(0.01)
            upload.cancel()
            await asyncio.sleep(0.02)
            assert not upload.done(), "Cancellation must not abandon a mutating worker"
            with pytest.raises(TurnBusy), SubmitterTurns(tmp_path).take(1, 0.02):
                pass
        finally:
            release.set()
        with pytest.raises(asyncio.CancelledError):
            await upload
        with SubmitterTurns(tmp_path).take(1, 0.1):
            pass

    asyncio.run(scenario())


def test_requests_are_limited_before_authentication_without_retaining_ips(tmp_path: Path) -> None:
    app = create_intake_app(tmp_path, Limits(auth_requests_per_second=0.01, auth_burst=2))
    client = TestClient(app)
    path = f"/reports/{new_id()}"
    assert client.get(path).status_code == 401
    assert client.get(path, headers={"Authorization": "Bearer wrong"}).status_code == 401
    refused = client.get(path)
    assert refused.status_code == 429
    assert int(refused.headers["Retry-After"]) > 0
