"""Submitter tokens are issued and revoked from the command line, never served (#57)."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from intake_helpers import jpeg, new_id, with_image

from weedz import tokens
from weedz.intake.api import create_intake_app
from weedz.intake.cli import main, parse
from weedz.intake.store import ReportStore
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


def test_an_overlong_token_id_is_refused_not_an_error(tmp_path: Path) -> None:
    assert Submitters(tmp_path).submitter("weedzsub_" + "9" * 30 + "_x") is None


def test_an_operator_can_withdraw_a_report_for_a_revoked_device(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A lost device's token is revoked, but its person can still have reports withdrawn."""
    credential = Submitters(tmp_path).issue("Lost phone")
    report_id = new_id()
    client = TestClient(create_intake_app(tmp_path))
    headers = {"Authorization": f"Bearer {credential.token}"}
    client.put(f"/reports/{report_id}", json=with_image(jpeg()), headers=headers)
    Submitters(tmp_path).revoke(credential.id)
    folder = ["--intake-dir", str(tmp_path)]
    main(["withdraw", "--submitter", str(credential.id), "--report", report_id, *folder])
    assert "Withdrew" in capsys.readouterr().out
    assert ReportStore(tmp_path).active() == []
    assert list((tmp_path / "reports" / "images").iterdir()) == []


def test_an_operator_withdrawal_before_the_report_arrives_refuses_it_later(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A PUT still in flight when the operator withdraws must not store the report after."""
    credential = Submitters(tmp_path).issue("Phone")
    report_id = new_id()
    folder = ["--intake-dir", str(tmp_path)]
    main(["withdraw", "--submitter", str(credential.id), "--report", report_id, *folder])
    assert "refused if it arrives" in capsys.readouterr().out
    client = TestClient(create_intake_app(tmp_path))
    headers = {"Authorization": f"Bearer {credential.token}"}
    late = client.put(f"/reports/{report_id}", json=with_image(jpeg()), headers=headers)
    assert late.status_code == 410
    assert ReportStore(tmp_path).active() == []
    assert list((tmp_path / "reports" / "images").iterdir()) == []


def test_the_token_lookup_runs_off_the_event_loop(tmp_path: Path) -> None:
    """FastAPI runs a sync dependency in its thread pool, so SQLite never blocks the loop."""
    import inspect

    from weedz.intake.submitters import require_submitter

    assert not inspect.iscoroutinefunction(require_submitter(Submitters(tmp_path)))
