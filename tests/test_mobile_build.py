"""Release preparation refuses invalid configuration without disclosing secret values."""

import base64
import json
import plistlib
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from weedz.mobile_build import BuildError, app_config, decode_secret, profile_info, write_private


def test_release_requires_both_https_urls_and_errors_name_only_the_setting() -> None:
    with pytest.raises(BuildError, match="WEEDZ_INTAKE_BASE_URL"):
        app_config({}, release=True)
    for value in ("http://pilot.invalid", "https://user:secret@pilot.invalid", "not-a-url"):
        with pytest.raises(BuildError) as error:
            app_config({"WEEDZ_INTAKE_BASE_URL": value}, release=True)
        assert value not in str(error.value)
    assert app_config({}, release=False) == {}
    config = {
        "WEEDZ_INTAKE_BASE_URL": "https://pilot.invalid",
        "WEEDZ_DELETION_REQUEST_URL": "https://pilot.invalid/delete",
    }
    assert app_config(config, release=True) == config


def test_decoding_refuses_empty_or_invalid_signing_material() -> None:
    for value in ("", "not-base64-secret!", base64.b64encode(b"").decode()):
        with pytest.raises(BuildError, match="KEYSTORE"):
            decode_secret({"KEYSTORE": value}, "KEYSTORE")
    assert decode_secret({"KEYSTORE": "a2V5\n"}, "KEYSTORE") == b"key"


def test_config_and_signing_files_are_private_from_creation(tmp_path: Path) -> None:
    path = tmp_path / "signing/config.json"
    write_private(path, json.dumps({"private": "value"}).encode())
    assert path.stat().st_mode & 0o077 == 0
    assert path.parent.stat().st_mode & 0o077 == 0
    with pytest.raises(FileExistsError):
        write_private(path, b"overwrite")


def profile(**changes: object) -> bytes:
    data = {
        "UUID": "00000000-0000-0000-0000-000000000001",
        "TeamIdentifier": ["ABCDE12345"],
        "ExpirationDate": (datetime.now(UTC) + timedelta(days=10)).replace(tzinfo=None),
        "Entitlements": {
            "application-identifier": "ABCDE12345.nz.weedz.app",
            "get-task-allow": False,
        },
        "DeveloperCertificates": [b"certificate"],
    }
    return plistlib.dumps(data | changes)


def test_distribution_profile_matches_explicit_team_bundle_and_expiry() -> None:
    assert profile_info(profile(), "ABCDE12345", "nz.weedz.app").uuid.endswith("0001")
    for changed in (
        {"TeamIdentifier": ["OTHER12345"]},
        {"ExpirationDate": datetime(2020, 1, 1)},
        {"ProvisionedDevices": ["device"]},
        {"ProvisionsAllDevices": True},
        {"Entitlements": {"application-identifier": "ABCDE12345.*"}},
        {"UUID": "../../bad"},
    ):
        with pytest.raises(BuildError):
            profile_info(profile(**changed), "ABCDE12345", "nz.weedz.app")
