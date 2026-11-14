"""A pilot run's reference collection is reachable from `main.py reference`."""

import json
from pathlib import Path

import pytest
from test_findings import finding, store_with_photo

from weedz.discovery import cli
from weedz.discovery.judgements import Judgement
from weedz.discovery.records import Finding
from weedz.reference_report import to_markdown


def reviewed_pilot(root: Path) -> str:
    """A screened photo: the suggestion confirmed by Ana, and Carol's gorse confirmed by Ben."""
    store, photo_id = store_with_photo(root)
    store.review("run", photo_id, "confirmed", "", "Ana")
    store.finding("run", photo_id, Finding.model_validate(finding(reviewer="Carol")))
    plant = store.findings("run", photo_id)[0]["id"]
    judgement = {"finding_id": plant, "dimension": "identity", "value": "confirmed"}
    store.judgement("run", photo_id, Judgement.model_validate(judgement | {"reviewer": "Ben"}))
    return photo_id


def test_cli_prints_markdown_and_writes_json(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    reviewed_pilot(tmp_path)
    destination = tmp_path / "out" / "reference.json"
    argv = ["reference", "--run", "run", "--pilot-dir", str(tmp_path)]
    cli.main([*argv, "--json", str(destination)])
    printed = capsys.readouterr().out
    assert printed.startswith("# Reference collection: run")
    result = json.loads(destination.read_text())
    assert result["standings"] == {"accepted": 2}
    suggestion, plant = result["examples"]
    assert (suggestion["origin"], suggestion["taxon"]) == ("model", "Clematis vitalba")
    assert not suggestion["uses"]["evaluation"]["eligible"]
    assert (plant["author"], plant["reviewers"]) == ("Carol", ["Ben"])
    assert plant["uses"]["evaluation"]["eligible"]
    # The fixture's location is obscured: never carried, and said to be withheld.
    assert plant["location"]["shareable"] is False
    # Every watchlist species is considered, even with no example.
    assert "Cortaderia selloana: no example eligible for training" in result["gaps"]


def test_cli_rejects_an_unknown_run(tmp_path: Path) -> None:
    reviewed_pilot(tmp_path)
    with pytest.raises(SystemExit, match="No run 'missing'"):
        cli.main(["reference", "--run", "missing", "--pilot-dir", str(tmp_path)])


def test_main_routes_the_reference_command(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from weedz import cli as entry

    argv = ["main.py", "reference", "--run", "run", "--pilot-dir", str(tmp_path / "none")]
    monkeypatch.setattr("sys.argv", argv)
    with pytest.raises(SystemExit, match="No pilot store"):
        entry.main()


def test_markdown_shows_standings_uses_coverage_gaps_and_what_is_not_recorded(
    tmp_path: Path,
) -> None:
    from weedz.adapters import pilot_samples
    from weedz.discovery.records import SPECIES
    from weedz.discovery.store import Store
    from weedz.reference import collection

    reviewed_pilot(tmp_path)
    result = collection("run", pilot_samples(Store(tmp_path), "run"), SPECIES)
    markdown = to_markdown(result)
    assert "| Accepted | 2 |" in markdown
    assert "| Evaluation | 1 |" in markdown
    assert "| Ulex europaeus | 1 | 1 | 1 |" in markdown
    assert "## Gaps" in markdown and "## Not recorded" in markdown
    assert "Growth stage" in markdown and "Habitat" in markdown


def test_a_free_text_taxon_cannot_split_a_markdown_table_cell() -> None:
    from test_reference import note, sample

    from weedz.reference import collection

    markdown = to_markdown(collection("run", [sample(note(taxon="Ulex | europaeus"))]))
    assert "| Ulex \\| europaeus | 1 | 1 | 1 |" in markdown
