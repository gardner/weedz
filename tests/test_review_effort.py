"""Reviewer effort is measured per decision and reported without inventing unmeasured time."""

import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from test_discovery import observation

from weedz.discovery.activities import export
from weedz.discovery.api import create_app
from weedz.discovery.effort import summarize_effort
from weedz.discovery.records import Review, RunSpec
from weedz.discovery.source import photo_from_observation
from weedz.discovery.store import Store


def store_with_photos(root: Path) -> tuple[Store, str, str]:
    store = Store(root)
    store.create_run("run", RunSpec())
    incidental = photo_from_observation(observation(), "Nelson", "incidental")
    reference = photo_from_observation(observation() | {"id": 200}, "Nelson", "reference")
    assert incidental is not None and reference is not None
    store.save_photos("run", [incidental, reference])
    return store, incidental.id, reference.id


def test_effort_is_stored_per_decision_and_optional(tmp_path: Path) -> None:
    store, photo_id, _ = store_with_photos(tmp_path)
    store.review("run", photo_id, "uncertain", "", "Ana", 42.5)
    store.review("run", photo_id, "rejected", "", "Ana")
    assert [event["effort_seconds"] for event in store.reviews("run", photo_id)] == [42.5, None]


def test_effort_must_be_a_plausible_duration() -> None:
    base = {"status": "confirmed", "reviewer": "Ana"}
    assert Review.model_validate(base).effort_seconds is None
    assert Review.model_validate(base | {"effort_seconds": 12.5}).effort_seconds == 12.5
    for invalid in [-1, 86_401]:
        with pytest.raises(ValidationError):
            Review.model_validate(base | {"effort_seconds": invalid})


def test_earlier_decisions_read_as_unmeasured_not_zero(tmp_path: Path) -> None:
    store, photo_id, _ = store_with_photos(tmp_path)
    with sqlite3.connect(tmp_path / "discovery.sqlite3") as db:
        db.execute("ALTER TABLE reviews DROP COLUMN effort_seconds")
        db.execute(
            "INSERT INTO reviews(run_id,photo_id,status,note,created_at,reviewer) "
            "VALUES(?,?,?,?,?,?)",
            ("run", photo_id, "uncertain", "", "2026-11-13T00:00:00+00:00", "Ana"),
        )
    assert Store(tmp_path).reviews("run", photo_id)[0]["effort_seconds"] is None


def test_summary_reports_time_by_status_reviewer_and_confirmed_photo(tmp_path: Path) -> None:
    store, incidental, reference = store_with_photos(tmp_path)
    store.review("run", incidental, "uncertain", "", "Ana", 60)
    store.review("run", incidental, "confirmed", "", "Ben", 120)
    store.review("run", reference, "rejected", "", "Ana", 30)
    store.review("run", reference, "rejected", "", "Ana")
    summary = summarize_effort(store.photos("run"), export(store, "run")["review_history"])
    assert summary["measured_decisions"] == 3
    assert summary["unmeasured_decisions"] == 1
    assert summary["total_minutes"] == 3.5
    assert summary["minutes_by_status"] == {"uncertain": 1.0, "confirmed": 2.0, "rejected": 0.5}
    assert summary["minutes_by_reviewer"] == {"Ana": 1.5, "Ben": 2.0}
    assert summary["incidental_minutes"] == 3.0
    assert summary["confirmed_incidental_photos"] == 1
    assert summary["incidental_minutes_per_confirmed_photo"] == 3.0


def test_no_confirmed_photo_means_no_per_finding_rate(tmp_path: Path) -> None:
    store, incidental, _ = store_with_photos(tmp_path)
    store.review("run", incidental, "rejected", "", "Ana", 30)
    summary = export(store, "run")["review_effort"]
    assert summary["incidental_minutes_per_confirmed_photo"] is None
    assert "not a measure of useful findings" in summary["meaning"]


def test_api_accepts_and_stores_effort(tmp_path: Path) -> None:
    _store, photo_id, _ = store_with_photos(tmp_path)
    client = TestClient(create_app(tmp_path))
    path = f"/runs/run/photos/{photo_id}"
    body = {"status": "rejected", "reviewer": "Ana", "effort_seconds": 9.5}
    assert client.post(f"{path}/review", json=body).status_code == 200
    assert client.get(f"{path}/reviews").json()[0]["effort_seconds"] == 9.5


def test_run_detail_includes_the_effort_summary(tmp_path: Path) -> None:
    store, photo_id, _ = store_with_photos(tmp_path)
    store.review("run", photo_id, "rejected", "", "Ana", 90)
    detail = TestClient(create_app(tmp_path)).get("/runs/run").json()
    assert detail["review_effort"]["total_minutes"] == 1.5


def test_untimed_incidental_decisions_withhold_the_per_finding_rate(tmp_path: Path) -> None:
    store, timed, _ = store_with_photos(tmp_path)
    untimed = photo_from_observation(observation() | {"id": 201}, "Nelson", "incidental")
    assert untimed is not None
    store.save_photos("run", [untimed])
    store.review("run", untimed.id, "confirmed", "", "Ana")
    store.review("run", timed, "confirmed", "", "Ana", 60)
    summary = export(store, "run")["review_effort"]
    assert summary["confirmed_incidental_photos"] == 2
    assert summary["unmeasured_incidental_decisions"] == 1
    assert summary["incidental_minutes_per_confirmed_photo"] is None


def test_untimed_reference_decisions_keep_the_per_finding_rate(tmp_path: Path) -> None:
    store, incidental, reference = store_with_photos(tmp_path)
    store.review("run", incidental, "confirmed", "", "Ana", 60)
    store.review("run", reference, "rejected", "", "Ana")
    summary = export(store, "run")["review_effort"]
    assert summary["unmeasured_decisions"] == 1
    assert summary["unmeasured_incidental_decisions"] == 0
    assert summary["incidental_minutes_per_confirmed_photo"] == 1.0
