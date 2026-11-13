from pathlib import Path

import pytest

from weedz import cli


def test_offline_fetch_does_not_access_network(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    def unexpected_fetch(root: Path) -> None:
        pytest.fail("--offline must never download data")

    monkeypatch.setattr(cli, "fetch_dataset", unexpected_fetch)
    monkeypatch.setattr("sys.argv", ["weedz", "fetch", "--offline", "--data-dir", str(tmp_path)])
    with pytest.raises(SystemExit) as error:
        cli.main()
    assert error.value.code == 1
    assert "fetch" in capsys.readouterr().err


@pytest.mark.parametrize("target", ["nan", "0", "1.1"])
def test_bad_recall_target_is_rejected_before_downloading(
    monkeypatch: pytest.MonkeyPatch, target: str
) -> None:
    def unexpected_fetch(root: Path) -> None:
        pytest.fail("Invalid arguments must not trigger downloads")

    monkeypatch.setattr(cli, "fetch_dataset", unexpected_fetch)
    monkeypatch.setattr("sys.argv", ["weedz", "--target-recall", target])
    with pytest.raises(SystemExit) as error:
        cli.main()
    assert error.value.code == 2
