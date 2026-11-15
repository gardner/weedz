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
    (source / "capture-provenance.json").write_text('{"photos": []}')
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


def test_replaced_snapshot_image_is_rejected_before_serving(tmp_path, monkeypatch):
    import json

    import pytest

    root = Path(__file__).parents[1]
    monkeypatch.syspath_prepend(str(root / "scripts"))
    spec = importlib.util.spec_from_file_location(
        "snapshot_images", root / "scripts/serve_demo_snapshot.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    source = tmp_path / "source"
    (source / "images").mkdir(parents=True)
    image = source / "images/photo.png"
    original = b"verified encoded pixels"
    image.write_bytes(b"different valid image")
    (source / "capture-provenance.json").write_text(
        json.dumps(
            {
                "photos": [
                    {"file": "images/photo.png", "sha256": hashlib.sha256(original).hexdigest()}
                ]
            }
        )
    )
    target = tmp_path / "target"
    target.mkdir()
    with pytest.raises(ValueError, match="checksum"):
        module.copy_verified_images(source, target)


def test_only_manifest_bound_image_bytes_are_copied(tmp_path, monkeypatch):
    import json

    root = Path(__file__).parents[1]
    monkeypatch.syspath_prepend(str(root / "scripts"))
    spec = importlib.util.spec_from_file_location(
        "verified_images", root / "scripts/serve_demo_snapshot.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    source = tmp_path / "source"
    (source / "images").mkdir(parents=True)
    raw = b"unchanged public encoded photo"
    (source / "images/kept.png").write_bytes(raw)
    (source / "images/unlisted.png").write_bytes(b"not part of the capture")
    (source / "capture-provenance.json").write_text(
        json.dumps(
            {"photos": [{"file": "images/kept.png", "sha256": hashlib.sha256(raw).hexdigest()}]}
        )
    )
    target = tmp_path / "target"
    target.mkdir()
    module.copy_verified_images(source, target)
    assert (target / "images/kept.png").read_bytes() == raw
    assert not (target / "images/unlisted.png").exists()


def test_matching_external_image_symlink_is_not_served(tmp_path, monkeypatch):
    import json

    import pytest

    root = Path(__file__).parents[1]
    monkeypatch.syspath_prepend(str(root / "scripts"))
    spec = importlib.util.spec_from_file_location(
        "confined_images", root / "scripts/serve_demo_snapshot.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    source = tmp_path / "source"
    (source / "images").mkdir(parents=True)
    external = tmp_path / "private-photo.png"
    external.write_bytes(b"external bytes stay unchanged")
    (source / "images/photo.png").symlink_to(external)
    (source / "capture-provenance.json").write_text(
        json.dumps(
            {
                "photos": [
                    {
                        "file": "images/photo.png",
                        "sha256": hashlib.sha256(external.read_bytes()).hexdigest(),
                    }
                ]
            }
        )
    )
    target = tmp_path / "target"
    target.mkdir()
    with pytest.raises(ValueError, match="escapes"):
        module.copy_verified_images(source, target)
    assert external.read_bytes() == b"external bytes stay unchanged"
    assert not (target / "images").exists()
