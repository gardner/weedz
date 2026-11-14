"""Reviewer invites are issued and revoked from the command line, never served."""

from pathlib import Path

import pytest

from weedz.discovery.access import Access
from weedz.discovery.access_cli import main
from weedz.discovery.cli import check_binding


def test_add_prints_the_token_once_and_list_never_does(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    main(["add", "--name", "Ana Smith", "--pilot-dir", str(tmp_path)])
    printed = capsys.readouterr().out
    [token] = [word for word in printed.split() if word.startswith("weedz_")]
    assert Access(tmp_path).reviewer(token) == "Ana Smith"
    main(["list", "--pilot-dir", str(tmp_path)])
    listing = capsys.readouterr().out
    assert "Ana Smith" in listing
    assert token.rsplit("_", 1)[-1] not in listing


def test_revoke_refuses_the_token_and_reports_unknown_ids(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    invite = Access(tmp_path).invite("Ana")
    main(["revoke", "--id", str(invite.id), "--pilot-dir", str(tmp_path)])
    assert "Revoked" in capsys.readouterr().out
    assert Access(tmp_path).reviewer(invite.token) is None
    with pytest.raises(SystemExit, match="No active invite"):
        main(["revoke", "--id", str(invite.id), "--pilot-dir", str(tmp_path)])


def test_add_refuses_an_empty_name(tmp_path: Path) -> None:
    with pytest.raises(SystemExit, match="name"):
        main(["add", "--name", "  ", "--pilot-dir", str(tmp_path)])


@pytest.mark.parametrize("host", ["127.0.0.1", "localhost", "::1"])
def test_local_mode_may_bind_loopback(host: str) -> None:
    check_binding("local", host)


@pytest.mark.parametrize("host", ["0.0.0.0", "192.168.1.5", "review.example.org", "::"])
def test_local_mode_refuses_to_listen_beyond_this_computer(host: str) -> None:
    with pytest.raises(SystemExit, match="--access tokens"):
        check_binding("local", host)
    check_binding("tokens", host)
