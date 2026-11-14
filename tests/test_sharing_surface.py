"""Every outbound path follows the sharing policy: export, run detail, images, store."""

import ast
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient
from test_discovery import observation
from test_judgements import PUBLIC, store_with_photo
from test_stratified_source import jpeg

from weedz.discovery import occurrences, source
from weedz.discovery.api import create_app
from weedz.discovery.records import Photo, RunSpec
from weedz.discovery.source import Inaturalist
from weedz.discovery.store import Store

SOURCE = Path(__file__).parents[1] / "src" / "weedz"


def force_licence(
    store: Store, photo_id: str, licence: str | None, field: str = "photo_license"
) -> None:
    """Store a record the way an older or other tool might have, past the store's check."""
    saved = Photo.model_validate(next(p for p in store.photos("run") if p["id"] == photo_id))
    record = saved.model_copy(update={field: licence or ""}).model_dump_json()
    with sqlite3.connect(store.root / "discovery.sqlite3") as db:
        db.execute("UPDATE photos SET record=? WHERE id=?", (record, photo_id))


def with_image(store: Store, photo_id: str) -> None:
    (store.root / "images").mkdir(exist_ok=True)
    (store.root / "images" / "101.jpg").write_bytes(jpeg())
    saved = Photo.model_validate(next(p for p in store.photos("run") if p["id"] == photo_id))
    store.save_photos("run", [saved.model_copy(update={"image_path": "images/101.jpg"})])


def test_the_downloaded_export_never_carries_an_obscured_point(tmp_path: Path) -> None:
    _store, _photo_id = store_with_photo(tmp_path)  # the default observation is obscured
    client = TestClient(create_app(tmp_path))
    [exported] = client.get("/runs/run/export").json()["photos"]
    assert exported["coordinate_status"] == "obscured"
    assert (exported["latitude"], exported["longitude"]) == (None, None)
    assert exported["sharing"]["terms"]["attribution"]
    detail = client.get("/runs/run").json()["photos"][0]
    assert (detail["latitude"], detail["longitude"]) == (None, None)


def test_the_downloaded_export_keeps_a_public_point_with_its_accuracy(tmp_path: Path) -> None:
    store_with_photo(tmp_path, **PUBLIC)
    exported = TestClient(create_app(tmp_path)).get("/runs/run/export").json()
    [shared] = exported["photos"]
    assert (shared["latitude"], shared["longitude"]) == (-41.2, 173.3)
    assert shared["positional_accuracy_m"] == 100
    assert exported["sharing"]


def test_the_review_app_sees_every_admitted_photo(tmp_path: Path) -> None:
    store, photo_id = store_with_photo(tmp_path)
    with_image(store, photo_id)
    response = TestClient(create_app(tmp_path)).get(f"/runs/run/photos/{photo_id}/image")
    assert response.status_code == 200
    assert response.content == jpeg()


def test_the_image_endpoint_refuses_a_licence_the_project_does_not_admit(tmp_path: Path) -> None:
    store, photo_id = store_with_photo(tmp_path)
    with_image(store, photo_id)
    force_licence(store, photo_id, "cc-by-nd")
    response = TestClient(create_app(tmp_path)).get(f"/runs/run/photos/{photo_id}/image")
    assert response.status_code == 403
    assert "no-derivatives" in response.json()["detail"].lower()


@pytest.mark.parametrize("field", ["photo_license", "observation_license"])
def test_the_store_refuses_a_photo_under_a_licence_not_admitted(tmp_path: Path, field: str) -> None:
    store = Store(tmp_path)
    store.create_run("run", RunSpec())
    photo = source.photo_from_observation(observation(), "Nelson", "incidental")
    assert photo is not None
    with pytest.raises(ValueError, match="Not admitted"):
        store.save_photos("run", [photo.model_copy(update={field: "cc-by-sa"})])
    assert store.photos("run") == []


def test_acquisition_and_reference_clients_only_read(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Nothing is published to iNaturalist or GBIF: every request a source makes is a GET."""
    monkeypatch.setattr(source.time, "sleep", lambda _seconds: None)
    methods: list[str] = []

    def handle(request: httpx.Request) -> httpx.Response:
        methods.append(request.method)
        if request.url.host == "api.inaturalist.org":
            return httpx.Response(200, json={"results": [observation()]})
        if request.url.host == "api.gbif.org":
            return httpx.Response(200, json={"results": [], "endOfRecords": True})
        return httpx.Response(200, content=jpeg())

    transport = httpx.MockTransport(handle)
    client = Inaturalist(tmp_path)
    client.client = httpx.Client(transport=transport)
    client.collect("run", RunSpec(sampling="recent", limit_per_region=1, controls_per_species=0))
    occurrences.fetch_snapshot(
        tmp_path, httpx.Client(transport=transport), datetime.now(UTC), pause=0
    )
    assert methods and set(methods) == {"GET"}


WRITES = {"post", "put", "patch", "delete"}


def _writes_to_source(path: Path) -> list[str]:
    """Write-method calls in a module that names an iNaturalist or GBIF host."""
    text = path.read_text()
    if "inaturalist.org" not in text and "gbif.org" not in text:
        return []
    return [
        f"{path.name}:{node.lineno}"
        for node in ast.walk(ast.parse(text))
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr in WRITES | {"request", "stream"}
    ]


def test_no_module_that_talks_to_a_source_can_write_to_it() -> None:
    found = [hit for path in SOURCE.rglob("*.py") for hit in _writes_to_source(path)]
    assert found == []
