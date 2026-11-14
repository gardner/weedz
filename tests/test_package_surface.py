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
from weedz.discovery.package_output import (
    Retained,
    archive,
    package_contents,
    texts,
    write,
)
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


def test_a_permitted_photo_is_packaged_from_its_retained_copy(tmp_path: Path) -> None:
    store, photo_id = selected_store(tmp_path)
    package, photos = package_contents(store, "run", "2026-11-14")
    # Photos are named by path, not held in memory, so large runs stream from disk.
    sha = hashlib.sha256(BYTES).hexdigest()
    assert photos == {f"photos/{photo_id}.jpg": Retained(tmp_path / "images" / "101.jpg", sha)}
    files = texts(package)
    assert json.loads(files["package.json"]) == package
    assert files["package.md"].decode().startswith("# Follow-up package: run")
    bundle = io.BytesIO()
    archive(package, photos, bundle)
    assert zipfile.ZipFile(bundle).read(f"photos/{photo_id}.jpg") == BYTES


def test_a_photo_whose_licence_does_not_permit_sharing_is_left_out(tmp_path: Path) -> None:
    store, _photo_id = selected_store(tmp_path, photo_license="cc-by-nd")
    _package, photos = package_contents(store, "run", "2026-11-14")
    assert photos == {}


def test_a_changed_or_missing_photo_is_linked_not_packaged(tmp_path: Path) -> None:
    store, _photo_id = selected_store(tmp_path)
    (tmp_path / "images" / "101.jpg").write_bytes(b"changed")
    package, photos = package_contents(store, "run", "2026-11-14")
    assert photos == {}
    image = package["leads"][0]["image"]
    assert image["included"] is False and image["file"] is None
    assert "no longer matches" in image["terms"]
    (tmp_path / "images" / "101.jpg").unlink()
    package, _photos = package_contents(store, "run", "2026-11-14")
    assert "no retained copy" in package["leads"][0]["image"]["terms"]
    assert "no retained copy" in texts(package)["package.md"].decode()


def test_a_photo_changed_after_checking_is_never_written(tmp_path: Path) -> None:
    store, _photo_id = selected_store(tmp_path)
    package, photos = package_contents(store, "run", "2026-11-14")
    (tmp_path / "images" / "101.jpg").write_bytes(b"changed since it was checked")
    with pytest.raises(ValueError, match="changed"):
        archive(package, photos, io.BytesIO())
    out = tmp_path / "out"
    with pytest.raises(ValueError, match="changed"):
        write(package, photos, out)
    # Nothing is left that could pass for a package, and the same folder can be retried.
    assert not out.exists()
    assert sorted(p.name for p in tmp_path.iterdir() if p.is_dir()) == ["images"]


def test_a_failed_cli_package_leaves_the_folder_ready_for_a_retry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from weedz.discovery import cli as module

    selected_store(tmp_path)
    out = tmp_path / "package"
    out.mkdir()
    checked = module.package_contents

    def then_deleted(*args: object) -> object:
        result = checked(*args)  # type: ignore[arg-type]
        (tmp_path / "images" / "101.jpg").unlink()
        return result

    monkeypatch.setattr(module, "package_contents", then_deleted)
    argv = ["package", "--run", "run", "--pilot-dir", str(tmp_path), "--out", str(out)]
    with pytest.raises(SystemExit, match="101.jpg"):
        cli.main(argv)
    assert out.is_dir() and not list(out.iterdir())
    monkeypatch.undo()
    cli.main(argv)  # the photo is now missing, so the lead links to it instead
    assert (out / "package.json").is_file() and not (out / "photos").exists()


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


def test_cli_refuses_a_file_as_the_output_folder(tmp_path: Path) -> None:
    selected_store(tmp_path)
    notes = tmp_path / "notes.txt"
    notes.write_text("keep")
    with pytest.raises(SystemExit, match="not a folder"):
        cli.main(["package", "--run", "run", "--pilot-dir", str(tmp_path), "--out", str(notes)])


def test_files_are_never_written_outside_the_output_folder(tmp_path: Path) -> None:
    source = tmp_path / "photo.jpg"
    source.write_bytes(BYTES)
    with pytest.raises(ValueError, match="outside"):
        escape = {"photos/../../escape.jpg": Retained(source, "")}
        write({"leads": []}, escape, tmp_path / "out")
    assert not (tmp_path / "escape.jpg").exists()


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


def test_the_archive_refuses_a_photo_changed_after_checking(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from weedz.discovery import api

    selected_store(tmp_path)
    checked = api.package_contents

    def then_changed(*args: object) -> object:
        result = checked(*args)  # type: ignore[arg-type]
        (tmp_path / "images" / "101.jpg").write_bytes(b"changed since it was checked")
        return result

    monkeypatch.setattr(api, "package_contents", then_changed)
    response = TestClient(create_app(tmp_path)).get("/runs/run/package/archive")
    assert response.status_code == 409 and "changed" in response.json()["detail"]


def test_the_written_folder_keeps_ordinary_permissions(tmp_path: Path) -> None:
    store, _photo_id = selected_store(tmp_path)
    package, photos = package_contents(store, "run", "2026-11-14")
    reference = tmp_path / "reference"
    reference.mkdir()
    write(package, photos, tmp_path / "new")
    assert (tmp_path / "new").stat().st_mode == reference.stat().st_mode
    chosen = tmp_path / "chosen"
    chosen.mkdir(mode=0o750)
    chosen.chmod(0o750)
    write(package, photos, chosen)
    assert chosen.stat().st_mode & 0o777 == 0o750


def test_the_archive_refuses_a_photo_deleted_after_checking(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from weedz.discovery import api

    selected_store(tmp_path)
    checked = api.package_contents

    def then_deleted(*args: object) -> object:
        result = checked(*args)  # type: ignore[arg-type]
        (tmp_path / "images" / "101.jpg").unlink()
        return result

    monkeypatch.setattr(api, "package_contents", then_deleted)
    response = TestClient(create_app(tmp_path)).get("/runs/run/package/archive")
    assert response.status_code == 409


def test_a_photo_that_cannot_be_read_is_linked_not_packaged(tmp_path: Path) -> None:
    store, _photo_id = selected_store(tmp_path)
    retained = tmp_path / "images" / "101.jpg"
    retained.chmod(0)
    try:
        package, photos = package_contents(store, "run", "2026-11-14")
    finally:
        retained.chmod(0o644)
    assert photos == {}
    assert "could not be read" in package["leads"][0]["image"]["terms"]
