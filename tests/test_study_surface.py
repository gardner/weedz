"""The study is reachable from the API, the run detail, the export and the CLI."""

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from test_outcomes_surface import pilot
from test_study import definition

from weedz.discovery import cli
from weedz.discovery.api import create_app


def body(author: str = "Ana", base: int = 0, **fields: object) -> dict:
    return {"definition": definition(**fields), "author": author, "base_version": base}


def test_api_creates_versions_lists_and_links_a_study(tmp_path: Path) -> None:
    pilot(tmp_path)
    client = TestClient(create_app(tmp_path))
    assert client.get("/runs/run/study").json() is None
    created = client.post("/studies", json=body())
    assert created.status_code == 201
    study_id = created.json()["id"]
    second = client.post(f"/studies/{study_id}/versions", json=body("Ben", 1, partner="B"))
    assert second.json() == {"id": study_id, "version": 2}
    stale = client.post(f"/studies/{study_id}/versions", json=body("Cat", 1))
    assert stale.status_code == 409
    assert "version 2" in stale.json()["detail"]
    assert client.post("/studies/study-none/versions", json=body(base=1)).status_code == 404
    shown = client.get(f"/studies/{study_id}").json()
    assert [item["version"] for item in shown["versions"]] == [1, 2]
    assert shown["current"]["definition"]["partner"] == "B"
    assert client.get("/studies/study-none").status_code == 404
    linked = client.post("/runs/run/study", json={"study_id": study_id, "linked_by": "Ana"})
    assert linked.status_code == 200
    assert client.get("/runs/run/study").json()["version"] == 2
    assert client.get("/studies").json()[0]["runs"] == ["run"]
    missing = client.post("/runs/run/study", json={"study_id": "study-none", "linked_by": "Ana"})
    assert missing.status_code == 404
    unknown = client.post("/runs/none/study", json={"study_id": study_id, "linked_by": "Ana"})
    assert unknown.status_code == 404


def test_a_new_study_can_be_linked_to_its_run_in_one_request(tmp_path: Path) -> None:
    pilot(tmp_path)
    client = TestClient(create_app(tmp_path))
    refused = client.post("/studies", json=body() | {"run_id": "none"})
    assert refused.status_code == 404
    assert client.get("/studies").json() == []
    created = client.post("/studies", json=body() | {"run_id": "run"}).json()
    linked = client.get("/runs/run/study").json()
    assert (linked["id"], linked["linked_by"]) == (created["id"], "Ana")


def test_api_refuses_an_unscreened_species_without_the_mark(tmp_path: Path) -> None:
    client = TestClient(create_app(tmp_path))
    refused = client.post("/studies", json=body(watchlist=[{"species": "Gunnera tinctoria"}]))
    assert refused.status_code == 422
    assert "not yet screened" in json.dumps(refused.json())


def test_run_detail_and_export_carry_the_study_and_budget_use(tmp_path: Path) -> None:
    pilot(tmp_path)
    client = TestClient(create_app(tmp_path))
    assert client.get("/runs/run").json()["study"] is None
    study_id = client.post("/studies", json=body(review_budget={"hours": 1})).json()["id"]
    client.post("/runs/run/study", json={"study_id": study_id, "linked_by": "Ana"})
    study = client.get("/runs/run").json()["study"]
    assert study["id"] == study_id
    # The fixture's one rejected decision took 90 seconds.
    assert study["budget_use"]["hours"]["used"] == 0.03
    assert study["budget_use"]["photos"]["state"] == "not set"
    shared = client.get("/runs/run/export").json()
    assert shared["study"]["definition"]["question"].startswith("Which overlooked")
    report = client.get("/runs/run/outcomes").json()
    assert report["study"]["id"] == study_id


def test_cli_records_a_version_links_it_and_shows_it(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    pilot(tmp_path)
    source = tmp_path / "study.json"
    source.write_text(json.dumps(definition()))
    args = ["study", "--run", "run", "--pilot-dir", str(tmp_path)]
    cli.main([*args, "--file", str(source), "--author", "Ana"])
    first = json.loads(capsys.readouterr().out)
    assert (first["version"], first["linked_by"]) == (1, "Ana")
    source.write_text(json.dumps(definition(partner="Changed")))
    cli.main([*args, "--file", str(source), "--author", "Ben", "--note", "New partner"])
    capsys.readouterr()
    cli.main(args)
    shown = json.loads(capsys.readouterr().out)
    assert (shown["id"], shown["version"]) == (first["id"], 2)
    assert shown["definition"]["partner"] == "Changed"
    assert shown["change_note"] == "New partner"


def test_cli_needs_an_author_to_record_and_refuses_an_invalid_file(tmp_path: Path) -> None:
    pilot(tmp_path)
    source = tmp_path / "study.json"
    source.write_text(json.dumps(definition(watchlist=[{"species": "Gunnera tinctoria"}])))
    args = ["study", "--run", "run", "--pilot-dir", str(tmp_path), "--file", str(source)]
    with pytest.raises(SystemExit, match="--author"):
        cli.main(args)
    with pytest.raises(SystemExit, match="not yet screened"):
        cli.main([*args, "--author", "Ana"])


def test_api_serves_the_screening_terms_a_study_is_checked_against(tmp_path: Path) -> None:
    terms = TestClient(create_app(tmp_path)).get("/studies/terms").json()
    assert terms["regions"] == ["Nelson", "Tasman"]
    assert terms["species"]["Clematis vitalba"] == "Old man's beard"
    lookalike = {"name": "Clematis paniculata", "confusable_with": "Clematis vitalba"}
    assert lookalike in terms["lookalikes"]
    assert terms["limits"]["coverage"] == {
        "measure": "Coverage and review usability",
        "direction": "at least",
        "unit": "% of incidental photos reviewed",
    }
