"""Submitter tokens are issued and revoked from the command line, never served (#57)."""

from pathlib import Path

import pytest

from weedz import tokens
from weedz.intake.cli import main, parse
from weedz.intake.submitters import Submitters


def test_add_prints_the_token_once_and_list_never_does(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    main(["add", "--label", "Pilot phone 1", "--intake-dir", str(tmp_path)])
    printed = capsys.readouterr().out
    [token] = [word for word in printed.split() if word.startswith("weedzsub_")]
    assert Submitters(tmp_path).submitter(token) is not None
    main(["list", "--intake-dir", str(tmp_path)])
    listing = capsys.readouterr().out
    assert "Pilot phone 1" in listing and "active" in listing
    assert token.rsplit("_", 1)[-1] not in listing


def test_revoke_refuses_the_token_and_reports_unknown_ids(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    credential = Submitters(tmp_path).issue("Phone")
    main(["revoke", "--id", str(credential.id), "--intake-dir", str(tmp_path)])
    assert "Revoked" in capsys.readouterr().out
    assert Submitters(tmp_path).submitter(credential.token) is None
    with pytest.raises(SystemExit, match="No active submitter"):
        main(["revoke", "--id", str(credential.id), "--intake-dir", str(tmp_path)])


def test_add_refuses_an_empty_label(tmp_path: Path) -> None:
    with pytest.raises(SystemExit, match="label"):
        main(["add", "--label", "  ", "--intake-dir", str(tmp_path)])


def test_serve_listens_on_this_computer_by_default() -> None:
    args = parse(["serve"])
    assert args.host == "127.0.0.1"
    assert args.intake_dir == Path("data/intake")


def test_main_dispatches_intake_commands(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    from weedz.cli import main as weedz_main

    monkeypatch.setattr("sys.argv", ["main.py", "intake", "list", "--intake-dir", str(tmp_path)])
    weedz_main()
    assert "No submitters issued yet." in capsys.readouterr().out


def test_submitter_hashes_are_compared_in_constant_time(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[tuple[str, str]] = []

    def compare(a: str, b: str) -> bool:
        calls.append((a, b))
        return a == b

    monkeypatch.setattr(tokens.hmac, "compare_digest", compare)
    submitters = Submitters(tmp_path)
    credential = submitters.issue("Phone")
    assert submitters.submitter(credential.token) == credential.id
    assert submitters.submitter(f"weedzsub_{credential.id}_wrong") is None
    # An unknown id still costs a comparison, so timing does not reveal which ids exist.
    assert submitters.submitter("weedzsub_99_wrong") is None
    assert len(calls) == 3
    assert (tmp_path / "submitters.sqlite3").stat().st_mode & 0o077 == 0
