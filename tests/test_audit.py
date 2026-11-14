"""A blind, rank-independent audit sample measures weeds that screening walked past."""

import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from test_discovery import observation

from weedz.discovery.activities import export
from weedz.discovery.api import create_app
from weedz.discovery.audit import audit_sample, summarize_audit
from weedz.discovery.records import Audit, RunSpec
from weedz.discovery.source import photo_from_observation
from weedz.discovery.store import Store


def photos(count: int, cohort: str = "incidental") -> list[dict]:
    return [{"id": f"p{index}", "cohort": cohort, "scores": {}} for index in range(count)]


def test_sample_is_deterministic_quarter_of_incidental_photos() -> None:
    sample = audit_sample("run", photos(24) + photos(3, "reference"))
    assert len(sample) == 6
    assert sample == audit_sample("run", list(reversed(photos(24))))
    assert sample != audit_sample("other-run", photos(24))
    assert len(audit_sample("run", photos(2))) == 1
    assert audit_sample("run", photos(0)) == set()


def test_sample_ignores_screening_scores() -> None:
    plain = photos(24)
    scored = [photo | {"scores": {"margin": float(index)}} for index, photo in enumerate(plain)]
    assert audit_sample("run", plain) == audit_sample("run", scored)


def test_audit_finding_must_be_a_watchlist_species_none_or_unsure() -> None:
    base = {"reviewer": "Ana"}
    for finding in ["Ulex europaeus", "none", "unsure"]:
        assert Audit.model_validate(base | {"finding": finding}).finding == finding
    with pytest.raises(ValidationError):
        Audit.model_validate(base | {"finding": "Turdus merula"})
    with pytest.raises(ValidationError):
        Audit.model_validate({"finding": "none", "reviewer": " "})


def test_summary_splits_found_weeds_into_flagged_and_missed() -> None:
    sampled = [
        {"id": "a", "cohort": "incidental", "scores": {"species": [margin("Ulex europaeus", 0.1)]}},
        {
            "id": "b",
            "cohort": "incidental",
            "scores": {"species": [margin("Ulex europaeus", -0.2)]},
        },
        {"id": "c", "cohort": "incidental", "scores": {}},
        {"id": "d", "cohort": "incidental", "scores": {}},
    ]
    latest = {
        "a": "Ulex europaeus",
        "b": "Ulex europaeus",
        "c": "none",
    }
    summary = summarize_audit(sampled, {"a", "b", "c", "d"}, latest)
    assert summary["sampled"] == 4
    assert summary["audited"] == 3
    assert summary["remaining"] == 1
    assert summary["weed_found"] == 2
    assert summary["flagged_by_screening"] == 1
    assert summary["missed_by_screening"] == 1
    assert "not expert-verified" in summary["meaning"]


def margin(name: str, value: float) -> dict:
    return {"name": name, "similarity": 0.3, "margin": value, "box": [0, 0, 1, 1]}


def run_with_photos(root: Path, count: int = 8) -> Store:
    store = Store(root)
    store.create_run("run", RunSpec())
    records = []
    for index in range(count):
        photo = photo_from_observation(observation() | {"id": 100 + index}, "Nelson", "incidental")
        assert photo is not None
        records.append(photo)
    store.save_photos("run", records)
    return store


def test_api_accepts_audits_only_for_sampled_photos(tmp_path: Path) -> None:
    store = run_with_photos(tmp_path)
    client = TestClient(create_app(tmp_path))
    detail = client.get("/runs/run").json()
    sampled = [photo["id"] for photo in detail["photos"] if photo["audit_sample"]]
    unsampled = [photo["id"] for photo in detail["photos"] if not photo["audit_sample"]]
    assert len(sampled) == 2
    body = {"finding": "none", "reviewer": "Ana", "effort_seconds": 12}
    assert client.post(f"/runs/run/photos/{unsampled[0]}/audit", json=body).status_code == 409
    assert client.post(f"/runs/run/photos/{sampled[0]}/audit", json=body).status_code == 200
    assert client.post("/runs/run/photos/missing/audit", json=body).status_code == 404
    [event] = store.audits("run", sampled[0])
    assert (event["reviewer"], event["finding"], event["effort_seconds"]) == ("Ana", "none", 12)
    detail = client.get("/runs/run").json()
    assert detail["audit"]["audited"] == 1
    assert export(store, "run")["audit"]["sampled"] == 2


def test_audits_table_is_added_to_existing_databases(tmp_path: Path) -> None:
    run_with_photos(tmp_path)
    with sqlite3.connect(tmp_path / "discovery.sqlite3") as db:
        db.execute("DROP TABLE audits")
    assert Store(tmp_path).latest_audits("run") == {}
