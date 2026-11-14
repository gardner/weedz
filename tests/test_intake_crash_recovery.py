"""A withdrawal's durable intent and live image writes survive interruptions (#97)."""

import sqlite3
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from intake_helpers import jpeg, new_id, with_image
from test_intake_concurrency import token

from weedz.intake.api import create_intake_app
from weedz.intake.store import ReportStore


def test_interrupted_withdrawal_is_hidden_and_resumed_at_startup(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    secret, report_id = token(tmp_path), new_id()
    headers, path = {"Authorization": f"Bearer {secret}"}, f"/reports/{report_id}"
    client, store = TestClient(create_intake_app(tmp_path)), ReportStore(tmp_path)
    assert client.put(path, json=with_image(jpeg()), headers=headers).status_code == 201

    def fail_sync() -> None:
        raise OSError("Interrupted before deletion completed")

    monkeypatch.setattr(store, "_sync_images", fail_sync)
    with pytest.raises(OSError):
        store.withdraw(1, report_id)
    assert store.active() == []
    assert client.get(path, headers=headers).json()["image"] is False
    # A fresh process/app has no in-memory knowledge of the interruption.
    restarted = TestClient(create_intake_app(tmp_path))
    assert restarted.get(path, headers=headers).json()["status"] == "withdrawn"
    assert restarted.put(path, json=with_image(jpeg()), headers=headers).status_code == 410
    assert list(store.images.iterdir()) == []
    with sqlite3.connect(store.path) as db:
        assert db.execute("SELECT body,content_sha256,image_file FROM reports").fetchone() == (
            None,
            None,
            None,
        )


def test_startup_sweep_does_not_delete_an_uncommitted_upload_crop(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    written, release = threading.Event(), threading.Event()
    original = ReportStore._write_image

    def paused(store: ReportStore, data: bytes) -> str:
        name = original(store, data)
        written.set()
        assert release.wait(5)
        return name

    secret = token(tmp_path)
    client = TestClient(create_intake_app(tmp_path))
    monkeypatch.setattr(ReportStore, "_write_image", paused)
    with ThreadPoolExecutor(2) as pool:
        upload = pool.submit(
            client.put,
            f"/reports/{new_id()}",
            json=with_image(jpeg()),
            headers={"Authorization": f"Bearer {secret}"},
        )
        assert written.wait(5)
        sweep = pool.submit(ReportStore(tmp_path).sweep)
        try:
            time.sleep(0.05)
            assert not sweep.done(), "Cleanup must wait for the crop's transaction to commit"
        finally:
            release.set()
        assert upload.result(timeout=5).status_code == 201
        sweep.result(timeout=5)
    stored = ReportStore(tmp_path).active()
    assert len(stored) == 1 and stored[0].image is not None
    assert stored[0].image.exists()
