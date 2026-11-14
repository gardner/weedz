"""Every review decision is attributed, and disagreement between reviewers stays visible."""

import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from test_discovery import observation

from weedz.discovery.api import create_app
from weedz.discovery.records import Review, RunSpec
from weedz.discovery.source import photo_from_observation
from weedz.discovery.store import Store


def store_with_photo(root: Path) -> tuple[Store, str]:
    store = Store(root)
    store.create_run("run", RunSpec())
    photo = photo_from_observation(observation(), "Nelson", "incidental")
    assert photo is not None
    store.save_photos("run", [photo])
    return store, photo.id


def test_each_decision_records_its_reviewer(tmp_path: Path) -> None:
    store, photo_id = store_with_photo(tmp_path)
    store.review("run", photo_id, "confirmed", "Seed heads visible", "Ana")
    [photo] = store.photos("run")
    assert photo["review_reviewer"] == "Ana"
    assert [event["reviewer"] for event in store.reviews("run", photo_id)] == ["Ana"]


def test_reviewers_holding_different_decisions_mark_the_photo_disputed(tmp_path: Path) -> None:
    store, photo_id = store_with_photo(tmp_path)
    store.review("run", photo_id, "confirmed", "", "Ana")
    assert store.photos("run")[0]["disputed"] is False
    store.review("run", photo_id, "rejected", "Native clematis", "Ben")
    [photo] = store.photos("run")
    assert photo["disputed"] is True
    assert photo["reviewer_decisions"] == {"Ana": "confirmed", "Ben": "rejected"}


def test_a_reviewer_changing_their_own_mind_is_not_a_dispute(tmp_path: Path) -> None:
    store, photo_id = store_with_photo(tmp_path)
    store.review("run", photo_id, "confirmed", "", "Ana")
    store.review("run", photo_id, "rejected", "Looked again", "Ana")
    store.review("run", photo_id, "rejected", "", "Ben")
    assert store.photos("run")[0]["disputed"] is False


def test_reopening_is_not_a_competing_decision(tmp_path: Path) -> None:
    store, photo_id = store_with_photo(tmp_path)
    store.review("run", photo_id, "confirmed", "", "Ana")
    store.review("run", photo_id, "unreviewed", "Second look", "Ben")
    assert store.photos("run")[0]["disputed"] is False


def test_review_requires_a_named_reviewer() -> None:
    with pytest.raises(ValidationError):
        Review.model_validate({"status": "confirmed", "reviewer": "   "})
    with pytest.raises(ValidationError):
        Review.model_validate({"status": "confirmed"})
    assert Review.model_validate({"status": "confirmed", "reviewer": " Ana "}).reviewer == "Ana"


def test_existing_history_is_kept_without_inventing_a_reviewer(tmp_path: Path) -> None:
    store, photo_id = store_with_photo(tmp_path)
    with sqlite3.connect(tmp_path / "discovery.sqlite3") as db:
        db.executescript("""
            ALTER TABLE reviews DROP COLUMN reviewer;
            ALTER TABLE photos DROP COLUMN review_reviewer;
        """)
        db.execute(
            "INSERT INTO reviews(run_id,photo_id,status,note,created_at) VALUES(?,?,?,?,?)",
            ("run", photo_id, "uncertain", "legacy", "2026-11-13T00:00:00+00:00"),
        )
    migrated = Store(tmp_path)
    assert migrated.reviews("run", photo_id)[0]["reviewer"] == ""
    migrated.review("run", photo_id, "confirmed", "", "Ana")
    assert migrated.photos("run")[0]["review_reviewer"] == "Ana"


def test_api_attributes_decisions_and_serves_history(tmp_path: Path) -> None:
    _store, photo_id = store_with_photo(tmp_path)
    client = TestClient(create_app(tmp_path))
    path = f"/runs/run/photos/{photo_id}"
    assert client.post(f"{path}/review", json={"status": "confirmed"}).status_code == 422
    assert (
        client.post(f"{path}/review", json={"status": "confirmed", "reviewer": "Ana"}).status_code
        == 200
    )
    history = client.get(f"{path}/reviews").json()
    assert [(event["reviewer"], event["status"]) for event in history] == [("Ana", "confirmed")]
    assert client.get("/runs/run/photos/missing/reviews").status_code == 404
