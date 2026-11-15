"""Serving capture evidence must leave its published files unchanged."""

import hashlib
import importlib.util
import sqlite3
from contextlib import closing
from pathlib import Path

from fastapi.testclient import TestClient

from weedz.discovery.store import Store


def test_serving_snapshot_leaves_published_database_unchanged(tmp_path, monkeypatch):
    root = Path(__file__).parents[1]
    monkeypatch.syspath_prepend(str(root / "scripts"))
    spec = importlib.util.spec_from_file_location(
        "serve_demo_snapshot", root / "scripts/serve_demo_snapshot.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    source = tmp_path / "published"
    Store(source)
    with closing(sqlite3.connect(source / "discovery.sqlite3")) as db:
        db.execute("PRAGMA journal_mode=DELETE")
    (source / "capture-provenance.json").write_text("{}")
    database = source / "discovery.sqlite3"
    before = hashlib.sha256(database.read_bytes()).hexdigest()
    files = set(source.rglob("*"))
    with module.snapshot_app(source, "owned-instance") as app:
        with TestClient(app) as client:
            assert client.get("/runs").status_code == 200
            assert client.get("/runs/capture_identity").json() == {
                "capture_instance": "owned-instance"
            }
            assert client.post("/runs", json={}).status_code == 405
        assert hashlib.sha256(database.read_bytes()).hexdigest() == before
        assert set(source.rglob("*")) == files
    assert hashlib.sha256(database.read_bytes()).hexdigest() == before
