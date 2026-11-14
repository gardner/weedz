"""A follow-up package is written as JSON, Markdown and permitted photos: API and CLI."""

import hashlib
import io
import json
import zipfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from test_judgements import store_with_photo
from test_leads import select

from weedz.discovery import cli
from weedz.discovery.api import create_app
from weedz.discovery.package_output import package_contents
from weedz.discovery.records import Photo
from weedz.discovery.store import Store

SCREENED = {"best_species": "Clematis vitalba", "width": 400, "height": 300}
BYTES = b"\xff\xd8 a retained photo \xff\xd9"


def with_image(store: Store, photo_id: str, **fields: object) -> None:
    (store.root / "images").mkdir(exist_ok=True)
    (store.root / "images" / "101.jpg").write_bytes(BYTES)
    saved = Photo.model_validate(next(p for p in store.photos("run") if p["id"] == photo_id))
    retained = {"image_path": "images/101.jpg", "sha256": hashlib.sha256(BYTES).hexdigest()}
    store.save_photos("run", [saved.model_copy(update=retained | fields)])


def selected_store(root: Path, **fields: object) -> tuple[Store, str]:
    store, photo_id = store_with_photo(root, SCREENED)
    with_image(store, photo_id, **fields)
    select(store, photo_id)
    return store, photo_id


def test_a_permitted_photo_is_packaged_with_its_retained_bytes(tmp_path: Path) -> None:
    store, photo_id = selected_store(tmp_path)
    package, files = package_contents(store, "run", "2026-11-14")
    assert files[f"photos/{photo_id}.jpg"] == BYTES
    assert json.loads(files["package.json"]) == package
    assert files["package.md"].decode().startswith("# Follow-up package: run")


def test_a_photo_whose_licence_does_not_permit_sharing_is_left_out(tmp_path: Path) -> None:
    store, _photo_id = selected_store(tmp_path, photo_license="cc-by-nd")
    _package, files = package_contents(store, "run", "2026-11-14")
    assert set(files) == {"package.json", "package.md"}


def test_a_photo_that_no_longer_matches_its_checksum_is_refused(tmp_path: Path) -> None:
    store, _photo_id = selected_store(tmp_path)
    (tmp_path / "images" / "101.jpg").write_bytes(b"changed")
    with pytest.raises(ValueError, match="checksum"):
        package_contents(store, "run", "2026-11-14")


def test_the_api_serves_the_package_and_its_archive(tmp_path: Path) -> None:
    _store, photo_id = selected_store(tmp_path)
    client = TestClient(create_app(tmp_path))
    package = client.get("/runs/run/package").json()
    assert [lead["photo_id"] for lead in package["leads"]] == [photo_id]
    response = client.get("/runs/run/package/archive")
    assert response.headers["content-type"] == "application/zip"
    assert "run-follow-up.zip" in response.headers["content-disposition"]
    names = zipfile.ZipFile(io.BytesIO(response.content)).namelist()
    assert sorted(names) == ["package.json", "package.md", f"photos/{photo_id}.jpg"]
    assert client.get("/runs/missing/package").status_code == 404
    assert client.get("/runs/missing/package/archive").status_code == 404


def test_cli_says_plainly_when_nothing_is_selected(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    store_with_photo(tmp_path, SCREENED)
    out = tmp_path / "package"
    cli.main(["package", "--run", "run", "--pilot-dir", str(tmp_path), "--out", str(out)])
    assert "No leads are selected for follow-up" in capsys.readouterr().out
    assert not out.exists()


def test_cli_writes_the_package_files(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    _store, photo_id = selected_store(tmp_path)
    out = tmp_path / "package"
    cli.main(["package", "--run", "run", "--pilot-dir", str(tmp_path), "--out", str(out)])
    assert (out / "photos" / f"{photo_id}.jpg").read_bytes() == BYTES
    assert json.loads((out / "package.json").read_text())["leads"][0]["photo_id"] == photo_id
    assert "Lead 1" in (out / "package.md").read_text()
    assert "1 lead" in capsys.readouterr().out
    with pytest.raises(SystemExit, match="not empty"):
        cli.main(["package", "--run", "run", "--pilot-dir", str(tmp_path), "--out", str(out)])


def test_cli_rejects_an_unknown_run(tmp_path: Path) -> None:
    store_with_photo(tmp_path, SCREENED)
    with pytest.raises(SystemExit, match="No run"):
        cli.main(["package", "--run", "missing", "--pilot-dir", str(tmp_path), "--out", "x"])


def test_main_routes_the_package_command(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from weedz import cli as entry

    argv = ["main.py", "package", "--run", "run", "--pilot-dir", str(tmp_path / "none")]
    monkeypatch.setattr("sys.argv", argv + ["--out", str(tmp_path / "out")])
    with pytest.raises(SystemExit, match="No pilot store"):
        entry.main()
