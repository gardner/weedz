"""Reviewers record a corrected species, its visible extent, or a plant the screening missed."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from test_discovery import observation

from weedz.discovery.activities import export
from weedz.discovery.api import create_app
from weedz.discovery.audit import audit_sample
from weedz.discovery.records import Finding, RunSpec
from weedz.discovery.source import photo_from_observation
from weedz.discovery.store import Store

SCREENED = {"best_species": "Clematis vitalba", "width": 400, "height": 300}


def store_with_photo(root: Path, scores: dict | None = SCREENED) -> tuple[Store, str]:
    store = Store(root)
    store.create_run("run", RunSpec())
    photo = photo_from_observation(observation(), "Nelson", "incidental")
    assert photo is not None
    store.save_photos("run", [photo])
    if scores:
        store.score("run", photo.id, scores)
    return store, photo.id


def finding(**fields: object) -> dict:
    return {"kind": "addition", "species": "Ulex europaeus", "reviewer": "Ana"} | fields


def test_a_finding_names_exactly_one_species_or_other_taxon() -> None:
    assert Finding.model_validate(finding()).other_taxon is None
    other = Finding.model_validate(finding(species=None, other_taxon=" Clematis paniculata "))
    assert (other.species, other.other_taxon) == (None, "Clematis paniculata")
    for invalid in [
        finding(species=None),
        finding(other_taxon="Clematis paniculata"),
        finding(species=None, other_taxon="   "),
        finding(species="Rubus fruticosus"),
        finding(kind="confirmation"),
        finding(reviewer=" "),
    ]:
        with pytest.raises(ValidationError):
            Finding.model_validate(invalid)


def test_free_text_is_never_mapped_to_a_watchlist_species() -> None:
    record = Finding.model_validate(finding(species=None, other_taxon="gorse"))
    assert (record.species, record.other_taxon) == (None, "gorse")


def test_a_box_must_be_ordered_and_non_empty() -> None:
    assert Finding.model_validate(finding(box=[10, 20, 110, 220])).box == (10, 20, 110, 220)
    for box in [[110, 20, 10, 220], [10, 20, 10, 220], [-1, 0, 5, 5], [1, 2, 3]]:
        with pytest.raises(ValidationError):
            Finding.model_validate(finding(box=box))


def test_findings_are_appended_with_attribution(tmp_path: Path) -> None:
    store, photo_id = store_with_photo(tmp_path)
    store.finding("run", photo_id, Finding.model_validate(finding(box=[1, 2, 30, 40])))
    store.finding(
        "run",
        photo_id,
        Finding.model_validate(
            finding(kind="correction", species=None, other_taxon="Clematis paniculata", note="n")
        ),
    )
    first, second = store.findings("run", photo_id)
    assert first["box"] == [1, 2, 30, 40] and first["reviewer"] == "Ana"
    assert second["box"] is None and second["other_taxon"] == "Clematis paniculata"
    assert second["species"] is None and second["note"] == "n" and second["created_at"]
    # In the run detail each recorded plant also carries its own judgements (#18).
    listed = store.photos("run")[0]["findings"]
    assert [listed[0] | first, listed[1] | second] == listed
    assert listed[0]["judgements"]["identity"] == {} and listed[0]["judgement_disputes"] == []


def test_api_records_and_lists_findings(tmp_path: Path) -> None:
    _store, photo_id = store_with_photo(tmp_path)
    client = TestClient(create_app(tmp_path))
    path = f"/runs/run/photos/{photo_id}/findings"
    body = finding(box=[0, 0, 400, 300], effort_seconds=12.5, note="Left edge")
    assert client.post(path, json=body).status_code == 200
    [saved] = client.get(path).json()
    assert saved["species"] == "Ulex europaeus" and saved["effort_seconds"] == 12.5
    assert client.get("/runs/run").json()["photos"][0]["findings"] == [saved]
    assert client.post("/runs/run/photos/missing/findings", json=body).status_code == 404
    assert client.get("/runs/run/photos/missing/findings").status_code == 404
    assert client.post(path, json=finding(reviewer="")).status_code == 422


def test_a_correction_names_a_different_species_from_the_suggestion(tmp_path: Path) -> None:
    _store, photo_id = store_with_photo(tmp_path)
    client = TestClient(create_app(tmp_path))
    path = f"/runs/run/photos/{photo_id}/findings"
    same = client.post(path, json=finding(kind="correction", species="Clematis vitalba"))
    assert same.status_code == 409
    for typed in ["Clematis vitalba", " clematis VITALBA ", "Old man's beard"]:
        retyped = finding(kind="correction", species=None, other_taxon=typed)
        assert client.post(path, json=retyped).status_code == 409, typed
    assert client.post(path, json=finding(kind="correction")).status_code == 200


def test_unscreened_photos_take_additions_but_no_correction_or_box(tmp_path: Path) -> None:
    _store, photo_id = store_with_photo(tmp_path, scores=None)
    client = TestClient(create_app(tmp_path))
    path = f"/runs/run/photos/{photo_id}/findings"
    assert client.post(path, json=finding(kind="correction")).status_code == 409
    assert client.post(path, json=finding(box=[0, 0, 5, 5])).status_code == 409
    assert client.post(path, json=finding()).status_code == 200


def test_a_box_must_lie_inside_the_image(tmp_path: Path) -> None:
    _store, photo_id = store_with_photo(tmp_path)
    client = TestClient(create_app(tmp_path))
    path = f"/runs/run/photos/{photo_id}/findings"
    assert client.post(path, json=finding(box=[0, 0, 401, 300])).status_code == 422
    assert client.post(path, json=finding(box=[0, 0, 400, 301])).status_code == 422


def test_export_carries_findings_and_counts_their_time(tmp_path: Path) -> None:
    store, photo_id = store_with_photo(tmp_path)
    store.review("run", photo_id, "rejected", "", "Ana", 30)
    store.finding("run", photo_id, Finding.model_validate(finding(effort_seconds=90)))
    store.finding("run", photo_id, Finding.model_validate(finding(reviewer="Ben")))
    result = export(store, "run")
    assert [item["reviewer"] for item in result["photos"][0]["findings"]] == ["Ana", "Ben"]
    effort = result["review_effort"]
    assert effort["total_minutes"] == 2.0
    assert effort["minutes_by_status"] == {"rejected": 0.5}
    assert effort["minutes_by_finding_kind"] == {"addition": 1.5}
    assert effort["minutes_by_reviewer"] == {"Ana": 2.0}
    assert (effort["measured_decisions"], effort["unmeasured_decisions"]) == (1, 0)
    assert (effort["measured_findings"], effort["unmeasured_findings"]) == (1, 1)
    assert any("not segmentation" in line for line in result["limitations"])


def sampled_photo(root: Path) -> tuple[Store, str]:
    store = Store(root)
    store.create_run("run", RunSpec())
    records = [
        photo_from_observation(observation() | {"id": 100 + index}, "Nelson", "incidental")
        for index in range(8)
    ]
    store.save_photos("run", [record for record in records if record is not None])
    return store, sorted(audit_sample("run", store.photos("run")))[0]


def test_a_finding_by_someone_who_had_not_audited_unblinds_later_audits(tmp_path: Path) -> None:
    store, target = sampled_photo(tmp_path)
    store.finding("run", target, Finding.model_validate(finding(reviewer="Carol")))
    store.audit("run", target, "Ulex europaeus", "", "Ana")
    assert store.latest_audits("run") == {}
    assert store.latest_audits("run", blind=False) == {target: {"Ana": "Ulex europaeus"}}


def test_a_finding_by_someone_who_already_audited_keeps_others_blind(tmp_path: Path) -> None:
    store, target = sampled_photo(tmp_path)
    store.audit("run", target, "none", "", "Carol")
    store.finding("run", target, Finding.model_validate(finding(reviewer="Carol")))
    store.audit("run", target, "Ulex europaeus", "", "Ana")
    assert store.latest_audits("run") == {target: {"Carol": "none", "Ana": "Ulex europaeus"}}


def test_untimed_findings_are_counted_apart_from_untimed_decisions(tmp_path: Path) -> None:
    store, photo_id = store_with_photo(tmp_path)
    store.review("run", photo_id, "confirmed", "", "Ana", 60)
    effort = export(store, "run")["review_effort"]
    assert effort["incidental_minutes_per_confirmed_photo"] == 1.0
    store.finding("run", photo_id, Finding.model_validate(finding()))
    effort = export(store, "run")["review_effort"]
    assert effort["unmeasured_incidental_decisions"] == 0
    assert effort["unmeasured_incidental_findings"] == 1
    # The rate would understate the cost, so it is withheld.
    assert effort["incidental_minutes_per_confirmed_photo"] is None
