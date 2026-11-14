from pathlib import Path

from fastapi.testclient import TestClient
from test_discovery import observation

from weedz.discovery.api import create_app
from weedz.discovery.records import RunSpec
from weedz.discovery.source import photo_from_observation
from weedz.discovery.store import Store


def test_review_api_persists_decision_and_rejects_unknown_photo(tmp_path: Path) -> None:
    store = Store(tmp_path)
    store.create_run("run", RunSpec())
    photo = photo_from_observation(observation(), "Nelson", "incidental")
    assert photo is not None
    store.save_photos("run", [photo])
    client = TestClient(create_app(tmp_path))
    response = client.post(
        f"/runs/run/photos/{photo.id}/review",
        json={
            "status": "uncertain",
            "note": "Need expert review",
            "reviewer": "Ana",
        },
    )
    assert response.status_code == 200
    assert client.get("/runs/run").json()["photos"][0]["review_status"] == "uncertain"
    assert (
        client.post(
            "/runs/run/photos/missing/review", json={"status": "confirmed", "reviewer": "Ana"}
        ).status_code
        == 404
    )
    assert (
        client.post(
            f"/runs/run/photos/{photo.id}/review", json={"status": "fake", "reviewer": "Ana"}
        ).status_code
        == 422
    )


def test_unknown_run_is_not_a_successful_empty_result(tmp_path: Path) -> None:
    client = TestClient(create_app(tmp_path))
    assert client.get("/runs/missing").status_code == 404
    assert client.get("/runs/missing/export").status_code == 404
