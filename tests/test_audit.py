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


def scored(pid: str, best: str | None = None, value: float | None = None) -> dict:
    scores = {} if best is None else {"best_species": best, "margin": value}
    return {"id": pid, "cohort": "incidental", "scores": scores}


def test_summary_reports_queue_rank_and_whether_the_find_was_the_suggestion() -> None:
    queue = [
        scored("a", "Ulex europaeus", 0.1),
        scored("b", "Cortaderia selloana", 0.3),
        scored("c", "Ulex europaeus", -0.2),
        scored("d"),
        {"id": "r", "cohort": "reference", "scores": {"margin": 9.0}},
    ]
    latest = {
        "a": {"Ana": "Ulex europaeus"},
        "b": {"Ana": "Ulex europaeus"},
        "c": {"Ana": "none"},
    }
    summary = summarize_audit(queue, {"a", "b", "c", "d"}, latest, {})
    assert summary["sampled"] == 4
    assert summary["audited"] == 3
    assert summary["remaining"] == 1
    assert summary["weed_found"] == 2
    assert summary["found_as_top_suggestion"] == 1
    assert summary["found_not_top_suggestion"] == 1
    assert summary["disputed"] == 0
    assert summary["findings"] == [
        {
            "photo_id": "a",
            "species": "Ulex europaeus",
            "top_suggestion": True,
            "queue_rank": 2,
            "queue_size": 4,
        },
        {
            "photo_id": "b",
            "species": "Ulex europaeus",
            "top_suggestion": False,
            "queue_rank": 1,
            "queue_size": 4,
        },
    ]
    assert "flagged_by_screening" not in summary
    assert "missed_by_screening" not in summary
    assert "not expert-verified" in summary["meaning"]
    assert "no calibrated detection threshold" in summary["meaning"]


def test_a_later_none_from_another_auditor_does_not_erase_a_found_weed(tmp_path: Path) -> None:
    store = run_with_photos(tmp_path)
    queue = store.photos("run")
    target = sorted(audit_sample("run", queue))[0]
    store.audit("run", target, "Ulex europaeus", "", "Ana")
    store.audit("run", target, "none", "", "Ben")
    summary = summarize_audit(queue, audit_sample("run", queue), store.latest_audits("run"), {})
    assert summary["audited"] == 1
    assert summary["weed_found"] == 1
    assert summary["disputed"] == 1


def test_only_an_auditors_first_answer_is_blind(tmp_path: Path) -> None:
    # After her first audit the photo is released into Ana's ranked queue, so a
    # re-answer may follow seeing the suggestion even without a recorded review.
    store = run_with_photos(tmp_path)
    target = sorted(audit_sample("run", store.photos("run")))[0]
    store.audit("run", target, "none", "", "Ana")
    store.audit("run", target, "Ulex europaeus", "", "Ana")
    assert store.latest_audits("run") == {target: {"Ana": "none"}}
    assert store.latest_audits("run", blind=False) == {target: {"Ana": "Ulex europaeus"}}


def test_a_review_by_someone_who_already_audited_does_not_unblind_others(
    tmp_path: Path,
) -> None:
    store = run_with_photos(tmp_path)
    target = sorted(audit_sample("run", store.photos("run")))[0]
    store.audit("run", target, "none", "", "Ana")
    store.review("run", target, "confirmed", "", "Ana")
    store.audit("run", target, "Ulex europaeus", "", "Ben")
    assert store.latest_audits("run") == {target: {"Ana": "none", "Ben": "Ulex europaeus"}}
    assert store.latest_audits("run", blind=False) == {}


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
    assert {photo["id"] for photo in detail["photos"] if photo["audited"]} == {sampled[0]}
    assert export(store, "run")["audit"]["sampled"] == 2


def test_audits_after_the_photo_was_reviewed_are_not_counted_as_blind(tmp_path: Path) -> None:
    store = run_with_photos(tmp_path, count=12)
    queue = store.photos("run")
    sample = audit_sample("run", queue)
    seen, fresh, *_ = sorted(sample)
    store.review("run", seen, "confirmed", "", "Carol")
    store.audit("run", seen, "Ulex europaeus", "", "Ana")
    store.audit("run", fresh, "Ulex europaeus", "", "Ana")
    store.review("run", fresh, "confirmed", "", "Ana")
    blind, late = store.latest_audits("run"), store.latest_audits("run", blind=False)
    assert set(blind) == {fresh}
    assert set(late) == {seen}
    summary = summarize_audit(queue, sample, blind, late)
    assert (summary["audited"], summary["weed_found"], summary["not_blind"]) == (1, 1, 1)
    assert "first answer" in summary["meaning"]


def test_detail_lists_who_audited_each_photo_without_findings(tmp_path: Path) -> None:
    store = run_with_photos(tmp_path)
    target = sorted(audit_sample("run", store.photos("run")))[0]
    store.audit("run", target, "none", "", "Ben")
    store.audit("run", target, "Ulex europaeus", "", "Ana")
    photos = TestClient(create_app(tmp_path)).get("/runs/run").json()["photos"]
    by_id = {photo["id"]: photo for photo in photos}
    assert by_id[target]["auditors"] == ["Ana", "Ben"]
    assert by_id[target]["audited"] is True
    assert all(photo["auditors"] == [] for photo in photos if photo["id"] != target)


def test_detail_keeps_audit_findings_blind_but_export_includes_them(tmp_path: Path) -> None:
    store = run_with_photos(tmp_path)
    target = sorted(audit_sample("run", store.photos("run")))[0]
    store.audit("run", target, "Ulex europaeus", "By the fence", "Ana")
    detail = TestClient(create_app(tmp_path)).get("/runs/run").json()
    assert detail["audit"]["weed_found"] == 1
    assert "findings" not in detail["audit"]
    assert "Ulex europaeus" not in str(detail["audit"])
    [finding] = export(store, "run")["audit"]["findings"]
    assert (finding["photo_id"], finding["species"]) == (target, "Ulex europaeus")


def test_audits_table_is_added_to_existing_databases(tmp_path: Path) -> None:
    run_with_photos(tmp_path)
    with sqlite3.connect(tmp_path / "discovery.sqlite3") as db:
        db.execute("DROP TABLE audits")
    assert Store(tmp_path).latest_audits("run") == {}
