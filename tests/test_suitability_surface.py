"""Source suitability is reachable from the API, the export and `main.py suitability`."""

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from test_outcomes_surface import pilot

from weedz.discovery import cli
from weedz.discovery.activities import export
from weedz.discovery.api import create_app
from weedz.discovery.store import Store


def test_api_serves_the_suitability_summary(tmp_path: Path) -> None:
    pilot(tmp_path)
    client = TestClient(create_app(tmp_path))
    report = client.get("/runs/run/suitability").json()
    assert report["run_id"] == "run"
    # The fixture's one photo has an obscured location and was reviewed, not screened.
    assert report["locations"]["not_searchable"]["obscured"]["photos"] == 1
    assert report["screening"]["not_screened"]["photos"] == 1
    assert report["screening"]["reviewed"]["photos"] == 1
    assert client.get("/runs/missing/suitability").status_code == 404


def test_the_export_and_shared_export_carry_the_summary(tmp_path: Path) -> None:
    pilot(tmp_path)
    summary = export(Store(tmp_path), "run")["source_suitability"]
    assert summary["permitted_uses"]["non_commercial_only"] == 1
    shared = TestClient(create_app(tmp_path)).get("/runs/run/export").json()
    assert shared["source_suitability"] == summary


def test_cli_prints_markdown_and_writes_json(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    pilot(tmp_path)
    destination = tmp_path / "out" / "suitability.json"
    argv = ["suitability", "--run", "run", "--pilot-dir", str(tmp_path)]
    cli.main([*argv, "--json", str(destination)])
    printed = capsys.readouterr().out
    assert printed.startswith("# Source suitability: run")
    assert "| A field search lead | 0 site visits + 1 ungrouped photo (1 photo) |" in printed
    assert json.loads(destination.read_text())["run_id"] == "run"


def test_cli_rejects_an_unknown_run(tmp_path: Path) -> None:
    pilot(tmp_path)
    with pytest.raises(SystemExit, match="No run 'missing'"):
        cli.main(["suitability", "--run", "missing", "--pilot-dir", str(tmp_path)])


def test_main_routes_the_suitability_command(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from weedz import cli as entry

    argv = ["main.py", "suitability", "--run", "run", "--pilot-dir", str(tmp_path / "none")]
    monkeypatch.setattr("sys.argv", argv)
    with pytest.raises(SystemExit, match="No pilot store"):
        entry.main()
