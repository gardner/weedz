"""The outcomes report is reachable from the API and from `uv run main.py outcomes`."""

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from test_discovery import observation

from weedz.discovery import cli
from weedz.discovery.api import create_app
from weedz.discovery.records import RunSpec
from weedz.discovery.source import photo_from_observation
from weedz.discovery.store import Store


def pilot(root: Path) -> str:
    store = Store(root)
    store.create_run("run", RunSpec())
    photo = photo_from_observation(observation(), "Nelson", "incidental")
    assert photo is not None
    store.save_photos("run", [photo])
    store.review("run", photo.id, "rejected", "", "Ana", 90)
    return photo.id


def test_api_serves_the_outcomes_report(tmp_path: Path) -> None:
    pilot(tmp_path)
    client = TestClient(create_app(tmp_path))
    report = client.get("/runs/run/outcomes").json()
    assert report["run_id"] == "run"
    alarms = next(item for item in report["measures"] if item["key"] == "false_alarm_workload")
    assert alarms["evidence"]["minutes"] == 1.5
    assert client.get("/runs/missing/outcomes").status_code == 404


def test_cli_prints_markdown_and_writes_json(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    pilot(tmp_path)
    destination = tmp_path / "out" / "outcomes.json"
    cli.main(["outcomes", "--run", "run", "--pilot-dir", str(tmp_path), "--json", str(destination)])
    printed = capsys.readouterr().out
    assert printed.startswith("# Pilot outcomes: run")
    assert json.loads(destination.read_text())["run_id"] == "run"


def test_cli_rejects_an_unknown_run(tmp_path: Path) -> None:
    pilot(tmp_path)
    with pytest.raises(SystemExit, match="No run 'missing'"):
        cli.main(["outcomes", "--run", "missing", "--pilot-dir", str(tmp_path)])


def test_cli_does_not_create_a_store_where_there_is_none(tmp_path: Path) -> None:
    empty = tmp_path / "nowhere"
    with pytest.raises(SystemExit, match="No pilot store"):
        cli.main(["outcomes", "--run", "run", "--pilot-dir", str(empty)])
    assert not empty.exists()


def test_main_routes_the_outcomes_command(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from weedz import cli as entry

    argv = ["main.py", "outcomes", "--run", "run", "--pilot-dir", str(tmp_path / "none")]
    monkeypatch.setattr("sys.argv", argv)
    with pytest.raises(SystemExit, match="No pilot store"):
        entry.main()
