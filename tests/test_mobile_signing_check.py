"""An explicit signing proof may be unconfigured, but production releases may not."""

import json
import subprocess
import sys
from pathlib import Path

import pytest

from weedz.mobile_build import BuildError, prepare


def test_signing_check_uses_empty_config_even_when_deployment_settings_exist(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    called: list[Path] = []

    def identity(root: Path, state: Path, env: object) -> None:
        called.append(state)

    monkeypatch.setattr("weedz.mobile_build.prepare_ios", identity)
    state = tmp_path / "state"
    prepare(
        "ios",
        tmp_path,
        state,
        {"WEEDZ_INTAKE_BASE_URL": "do-not-embed-this", "WEEDZ_DELETION_REQUEST_URL": "ignored"},
        ios_signing_check=True,
    )
    assert json.loads((state / "config.json").read_text()) == {}
    assert called == [state]


def test_signing_check_cannot_enable_android_or_production_release(tmp_path: Path) -> None:
    for platform, release in (("android", False), ("ios", True)):
        with pytest.raises(BuildError, match="signing check"):
            prepare(
                platform, tmp_path, tmp_path / "state", {}, release=release, ios_signing_check=True
            )
    assert not (tmp_path / "state").exists()


def test_production_urls_are_still_required_before_signing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def identity(root: Path, state: Path, env: object) -> None:
        pytest.fail("must validate production configuration first")

    monkeypatch.setattr("weedz.mobile_build.prepare_ios", identity)
    with pytest.raises(BuildError, match="WEEDZ_INTAKE_BASE_URL"):
        prepare("ios", tmp_path, tmp_path / "state", {}, release=True)
    assert not (tmp_path / "state").exists()


def test_command_line_modes_are_mutually_exclusive(tmp_path: Path) -> None:
    script = Path(__file__).parents[1] / "src/weedz/mobile_build.py"
    result = subprocess.run(
        [
            sys.executable,
            str(script),
            "ios",
            "--state",
            str(tmp_path),
            "--release",
            "--ios-signing-check",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 2
    assert "not allowed with argument" in result.stderr
