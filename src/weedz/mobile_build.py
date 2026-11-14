"""Prepare private mobile CI configuration/signing files; never print secret values.

Run directly with Python on Actions runners; only the standard library is needed.
Cleanup is a separate always-run step, including after a failed preparation/build.
"""

import argparse
import base64
import hashlib
import json
import os
import plistlib
import re
import secrets
import shutil
import subprocess
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import NamedTuple
from urllib.parse import urlsplit

URL_NAMES = ("WEEDZ_INTAKE_BASE_URL", "WEEDZ_DELETION_REQUEST_URL")
ANDROID_NAMES = (
    "ANDROID_APPLICATION_ID",
    "ANDROID_KEYSTORE_BASE64",
    "ANDROID_KEYSTORE_PASSWORD",
    "ANDROID_KEY_ALIAS",
    "ANDROID_KEY_PASSWORD",
)
IOS_NAMES = (
    "IOS_BUNDLE_IDENTIFIER",
    "APPLE_TEAM_ID",
    "IOS_DISTRIBUTION_P12_BASE64",
    "IOS_DISTRIBUTION_P12_PASSWORD",
    "IOS_PROVISIONING_PROFILE_BASE64",
)


class BuildError(ValueError):
    """An actionable configuration error that contains names, never supplied values."""


def required(env: Mapping[str, str], names: tuple[str, ...]) -> None:
    missing = [name for name in names if not env.get(name)]
    if missing:
        raise BuildError("Configure Actions secrets: " + ", ".join(missing))


def app_config(env: Mapping[str, str], *, release: bool) -> dict[str, str]:
    if release:
        required(env, URL_NAMES)
    result = {}
    for name in URL_NAMES:
        value = env.get(name, "")
        if not value:
            continue
        validate_url(value, name)
        result[name] = value
    return result


def validate_url(value: str, name: str) -> None:
    try:
        parsed = urlsplit(value)
        _ = parsed.port  # Validate non-numeric/out-of-range ports without exposing the input.
    except ValueError:
        raise BuildError(f"{name} must be a valid HTTPS URL") from None
    invalid = (
        parsed.scheme != "https",
        not parsed.hostname,
        bool(parsed.username),
        bool(parsed.password),
        bool(parsed.fragment),
        bool(re.search(r"\s", value)),
        name == "WEEDZ_INTAKE_BASE_URL" and bool(parsed.query),
    )
    if any(invalid):
        raise BuildError(f"{name} must be HTTPS without credentials/fragment or an intake query")


def decode_secret(env: Mapping[str, str], name: str) -> bytes:
    try:
        data = base64.b64decode("".join(env.get(name, "").split()), validate=True)
    except ValueError as error:
        raise BuildError(f"{name} must contain base64 signing material") from error
    if not data:
        raise BuildError(f"{name} must contain nonempty signing material")
    return data


def write_private(path: Path, data: bytes) -> None:
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "wb") as output:
        output.write(data)


def identifier(value: str, name: str, *, android: bool = False) -> str:
    segment = r"[A-Za-z][A-Za-z0-9_]*" if android else r"[A-Za-z0-9-]+"
    if not re.fullmatch(rf"{segment}(\.{segment})+", value) or value.startswith("org.example."):
        raise BuildError(f"{name} must be a final application identifier you control")
    return value


class ProfileInfo(NamedTuple):
    uuid: str
    certificates: tuple[str, ...]


def profile_info(data: bytes, team: str, bundle: str) -> ProfileInfo:
    try:
        profile = plistlib.loads(data)
        entitlements = profile["Entitlements"]
        expires = profile["ExpirationDate"].replace(tzinfo=UTC)
        certificates = tuple(
            hashlib.sha1(cert).hexdigest().upper() for cert in profile["DeveloperCertificates"]
        )
        uuid = profile["UUID"]
    except (ValueError, TypeError, KeyError, AttributeError) as error:
        raise BuildError("IOS_PROVISIONING_PROFILE_BASE64 is not a valid profile") from error
    if not isinstance(uuid, str) or not re.fullmatch(r"[A-Fa-f0-9-]{36}", uuid):
        raise BuildError("Provisioning profile has an invalid UUID")
    if (
        profile.get("TeamIdentifier") != [team]
        or entitlements.get("application-identifier") != f"{team}.{bundle}"
    ):
        raise BuildError("Provisioning profile must match APPLE_TEAM_ID and IOS_BUNDLE_IDENTIFIER")
    if expires <= datetime.now(UTC):
        raise BuildError("Provisioning profile has expired")
    if (
        profile.get("ProvisionedDevices")
        or profile.get("ProvisionsAllDevices")
        or entitlements.get("get-task-allow")
    ):
        raise BuildError("Use an App Store distribution provisioning profile")
    if not certificates:
        raise BuildError("Provisioning profile contains no distribution certificates")
    return ProfileInfo(uuid, certificates)


def run(args: list[str]) -> bytes:
    try:
        return subprocess.run(args, check=True, capture_output=True).stdout
    except (OSError, subprocess.CalledProcessError) as error:
        # Tool stderr can contain secrets or signing material. Never echo it or argv.
        raise BuildError(
            f"{Path(args[0]).name} operation failed; check signing configuration"
        ) from error


def prepare_android(state: Path, env: Mapping[str, str]) -> None:
    required(env, ANDROID_NAMES)
    identifier(env["ANDROID_APPLICATION_ID"], "ANDROID_APPLICATION_ID", android=True)
    write_private(state / "android/upload.jks", decode_secret(env, "ANDROID_KEYSTORE_BASE64"))


def install_identity(state: Path, env: Mapping[str, str], profile: ProfileInfo) -> None:
    keychain = str(state / "ios/signing.keychain-db")
    password = secrets.token_urlsafe(32)
    original = run(["security", "list-keychains", "-d", "user"])
    write_private(
        state / "ios/keychains.json",
        json.dumps(re.findall(r'"([^"]+)"', original.decode())).encode(),
    )
    run(["security", "create-keychain", "-p", password, keychain])
    run(["security", "set-keychain-settings", "-lut", "21600", keychain])
    run(["security", "unlock-keychain", "-p", password, keychain])
    previous = json.loads((state / "ios/keychains.json").read_text())
    run(["security", "list-keychains", "-d", "user", "-s", *previous, keychain])
    run(
        [
            "security",
            "import",
            str(state / "ios/distribution.p12"),
            "-k",
            keychain,
            "-P",
            env["IOS_DISTRIBUTION_P12_PASSWORD"],
            "-T",
            "/usr/bin/codesign",
            "-T",
            "/usr/bin/security",
        ]
    )
    run(
        [
            "security",
            "set-key-partition-list",
            "-S",
            "apple-tool:,apple:,codesign:",
            "-k",
            password,
            keychain,
        ]
    )
    identities = run(["security", "find-identity", "-v", "-p", "codesigning", keychain]).decode()
    if not any(fingerprint in identities for fingerprint in profile.certificates):
        raise BuildError("Distribution private key/certificate must match the provisioning profile")


def prepare_ios(root: Path, state: Path, env: Mapping[str, str]) -> None:
    required(env, IOS_NAMES)
    bundle = identifier(env["IOS_BUNDLE_IDENTIFIER"], "IOS_BUNDLE_IDENTIFIER")
    team = env["APPLE_TEAM_ID"]
    if not re.fullmatch(r"[A-Z0-9]{10}", team):
        raise BuildError("APPLE_TEAM_ID must be a ten-character Apple team id")
    write_private(state / "ios/distribution.p12", decode_secret(env, "IOS_DISTRIBUTION_P12_BASE64"))
    profile_path = state / "ios/profile.mobileprovision"
    write_private(profile_path, decode_secret(env, "IOS_PROVISIONING_PROFILE_BASE64"))
    info = profile_info(run(["security", "cms", "-D", "-i", str(profile_path)]), team, bundle)
    install_identity(state, env, info)
    folder = Path.home() / "Library/MobileDevice/Provisioning Profiles"
    installed = folder / f"{info.uuid}.mobileprovision"
    if installed.exists():
        raise BuildError("Provisioning profile is already installed; use a clean runner")
    write_private(state / "ios/installed-profile.json", json.dumps(str(installed)).encode())
    write_private(installed, profile_path.read_bytes())
    signing = (
        f"WEEDZ_BUNDLE_IDENTIFIER = {bundle}\nWEEDZ_CODE_SIGN_IDENTITY = Apple Distribution\n"
        f"DEVELOPMENT_TEAM = {team}\nCODE_SIGN_STYLE = Manual\n"
        f"PROVISIONING_PROFILE_SPECIFIER = {info.uuid}\n"
        f'OTHER_CODE_SIGN_FLAGS = $(inherited) --keychain "{state / "ios/signing.keychain-db"}"\n'
    )
    write_private(root / "mobile/ios/Flutter/Signing.xcconfig", signing.encode())
    export = {
        "method": "app-store-connect",
        "teamID": team,
        "signingStyle": "manual",
        "signingCertificate": "Apple Distribution",
        "provisioningProfiles": {bundle: info.uuid},
        "uploadSymbols": False,
        "manageAppVersionAndBuildNumber": False,
    }
    write_private(state / "ios/ExportOptions.plist", plistlib.dumps(export))


def ios_cleanup_operations(root: Path, state: Path) -> list[Callable[[], object]]:
    operations: list[Callable[[], object]] = []
    operations.append(
        lambda: (root / "mobile/ios/Flutter/Signing.xcconfig").unlink(missing_ok=True)
    )
    installed = state / "ios/installed-profile.json"
    if installed.exists():
        operations.append(lambda: Path(json.loads(installed.read_text())).unlink(missing_ok=True))
    previous = state / "ios/keychains.json"
    if previous.exists():
        operations.append(
            lambda: run(
                [
                    "security",
                    "list-keychains",
                    "-d",
                    "user",
                    "-s",
                    *json.loads(previous.read_text()),
                ]
            )
        )
    keychain = state / "ios/signing.keychain-db"
    if keychain.exists():
        operations.append(lambda: run(["security", "delete-keychain", str(keychain)]))
    return operations


def cleanup(root: Path, state: Path, platform: str) -> None:
    operations = ios_cleanup_operations(root, state) if platform == "ios" else []
    if state.exists():
        operations.append(lambda: shutil.rmtree(state))
    failed = False
    for operation in operations:
        try:
            operation()
        except (BuildError, OSError, ValueError):
            failed = True  # Attempt every cleanup even when an earlier operation failed.
    if failed:
        raise BuildError("Signing cleanup failed; check the temporary runner before reuse")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("platform", choices=("android", "ios"))
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--state", type=Path, required=True)
    parser.add_argument("--release", action="store_true")
    parser.add_argument("--cleanup", action="store_true")
    args = parser.parse_args()
    try:
        if args.cleanup:
            cleanup(args.root, args.state, args.platform)
            return
        config = app_config(os.environ, release=args.release)
        write_private(args.state / "config.json", json.dumps(config).encode())
        if args.release and args.platform == "android":
            prepare_android(args.state, os.environ)
        if args.release and args.platform == "ios":
            prepare_ios(args.root, args.state, os.environ)
    except BuildError as error:
        raise SystemExit(str(error)) from None


if __name__ == "__main__":
    main()
