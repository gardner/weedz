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


def test_android_preparation_refuses_template_identifiers_before_writing(tmp_path: Path) -> None:
    from weedz.mobile_build import prepare_android

    env = {
        "ANDROID_APPLICATION_ID": "org.example.weedz",
        "ANDROID_KEYSTORE_BASE64": base64.b64encode(b"key").decode(),
        "ANDROID_KEYSTORE_PASSWORD": "store-secret",
        "ANDROID_KEY_ALIAS": "upload",
        "ANDROID_KEY_PASSWORD": "key-secret",
    }
    with pytest.raises(BuildError, match="ANDROID_APPLICATION_ID"):
        prepare_android(tmp_path, env)
    assert not (tmp_path / "android/upload.jks").exists()
    prepare_android(tmp_path, env | {"ANDROID_APPLICATION_ID": "nz.weedz.pilot"})
    assert (tmp_path / "android/upload.jks").read_bytes() == b"key"


def test_cleanup_attempts_keychain_deletion_even_if_restoring_search_list_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from weedz.mobile_build import cleanup

    state = tmp_path / "temporary"
    write_private(state / "ios/keychains.json", b'["original.keychain-db"]')
    write_private(state / "ios/signing.keychain-db", b"secret")
    deleted: list[str] = []

    def security(args: list[str]) -> bytes:
        if args[1] == "list-keychains":
            raise BuildError("simulated restoration failure")
        if args[1] == "delete-keychain":
            deleted.append(args[-1])
        return b""

    monkeypatch.setattr("weedz.mobile_build.run", security)
    with pytest.raises(BuildError):
        cleanup(tmp_path, state, "ios")
    assert deleted == [str(state / "ios/signing.keychain-db")]
    assert not state.exists()


def test_ios_preparation_and_cleanup_with_a_matching_private_identity(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import hashlib

    from weedz.mobile_build import cleanup, prepare_ios

    monkeypatch.setattr(Path, "home", lambda: tmp_path / "home")
    state = tmp_path / "temporary"
    root = tmp_path / "repository"
    identity = hashlib.sha1(b"certificate").hexdigest().upper()
    calls: list[list[str]] = []

    def security(args: list[str]) -> bytes:
        calls.append(args)
        if args[1] == "cms":
            return profile()
        if args[1] == "list-keychains" and "-s" not in args:
            return b'"original.keychain-db"\n'
        if args[1] == "create-keychain":
            Path(args[-1]).write_bytes(b"temporary keychain")
        if args[1] == "find-identity":
            return f'1) {identity} "Apple Distribution"'.encode()
        return b""

    monkeypatch.setattr("weedz.mobile_build.run", security)
    env = {
        "IOS_BUNDLE_IDENTIFIER": "nz.weedz.app",
        "APPLE_TEAM_ID": "ABCDE12345",
        "IOS_DISTRIBUTION_P12_BASE64": base64.b64encode(b"p12").decode(),
        "IOS_DISTRIBUTION_P12_PASSWORD": "password",
        "IOS_PROVISIONING_PROFILE_BASE64": base64.b64encode(b"cms").decode(),
    }
    prepare_ios(root, state, env)
    export = plistlib.loads((state / "ios/ExportOptions.plist").read_bytes())
    assert export["method"] == "app-store-connect"
    assert export["provisioningProfiles"] == {
        "nz.weedz.app": "00000000-0000-0000-0000-000000000001"
    }
    assert "CODE_SIGN_STYLE = Manual" in (root / "mobile/ios/Flutter/Signing.xcconfig").read_text()
    installed = Path(json.loads((state / "ios/installed-profile.json").read_text()))
    assert installed.exists()
    cleanup(root, state, "ios")
    assert not installed.exists()
    assert not state.exists()
    assert not (root / "mobile/ios/Flutter/Signing.xcconfig").exists()
    assert ["security", "list-keychains", "-d", "user", "-s", "original.keychain-db"] in calls
    assert any(args[1] == "delete-keychain" for args in calls)


def test_urls_refuse_bad_ports_ipv6_and_intake_queries_without_echoing_values() -> None:
    for value in (
        "https://pilot.invalid:wrong",
        "https://pilot.invalid:99999",
        "https://[malformed-private",
        "https://pilot.invalid?credential=private",
        "https://pilot.invalid\n/private",
    ):
        with pytest.raises(BuildError, match="WEEDZ_INTAKE_BASE_URL") as error:
            app_config({"WEEDZ_INTAKE_BASE_URL": value}, release=False)
        assert value not in str(error.value)
    contact = {"WEEDZ_DELETION_REQUEST_URL": "https://pilot.invalid/form?type=delete"}
    assert app_config(contact, release=False) == contact
