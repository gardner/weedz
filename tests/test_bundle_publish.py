"""Publishing a signed bundle, serving it, and keeping the signing key out of the repo (#59)."""

import json
import logging
import os
import subprocess
from datetime import date
from pathlib import Path

import pytest
from bundle_helpers import parity_benchmark, spec, write_artefacts
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from fastapi.testclient import TestClient

from weedz.bundles.api import create_app
from weedz.bundles.cli import main
from weedz.bundles.manifest import BundleRejected, ParityRefused, check_artefact, read_manifest
from weedz.bundles.publish import lock, publish
from weedz.bundles.signing import KeyRefused, generate_key, load_private_key, public_key_text

REPO = Path(__file__).resolve().parents[1]


@pytest.fixture
def key_path(tmp_path: Path) -> Path:
    path = tmp_path / "keys" / "bundle.ed25519"
    generate_key(path)
    return path


def _private_key_text(path: Path) -> str:
    return "".join(path.read_text().splitlines()[1:-1])


def test_a_new_key_is_owner_only_and_only_its_public_half_is_shown(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.DEBUG)
    path = tmp_path / "keys" / "bundle.ed25519"
    main(["keygen", "--key", str(path)])
    assert path.stat().st_mode & 0o777 == 0o600
    shown = capsys.readouterr()
    secret = _private_key_text(path)
    assert "public key" in shown.out
    assert secret not in shown.out + shown.err + caplog.text


def test_a_key_is_never_written_inside_a_git_work_tree(tmp_path: Path) -> None:
    with pytest.raises(KeyRefused, match="git"):
        generate_key(REPO / "bundle.ed25519")
    assert not (REPO / "bundle.ed25519").exists()
    nested = tmp_path / "project" / "deep"
    nested.mkdir(parents=True)
    (tmp_path / "project" / ".git").mkdir()
    with pytest.raises(KeyRefused, match="git"):
        generate_key(nested / "bundle.ed25519")


def test_an_existing_or_readable_key_is_refused(tmp_path: Path, key_path: Path) -> None:
    with pytest.raises(KeyRefused, match="exists"):
        generate_key(key_path)
    os.chmod(key_path, 0o644)
    with pytest.raises(KeyRefused, match="readable"):
        load_private_key(key_path)


def test_no_private_key_is_tracked_in_the_repo() -> None:
    tracked = subprocess.run(
        # A pattern, not the literal marker, so this file does not match itself.
        ["git", "grep", "-lE", "BEGIN [A-Z ]*PRIVATE KEY"],
        cwd=REPO,
        capture_output=True,
        text=True,
    )
    assert tracked.stdout.strip() == ""


def test_publishing_writes_content_addressed_artefacts_and_a_verifiable_manifest(
    tmp_path: Path, key_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.DEBUG)
    out = tmp_path / "site"
    public = publish(spec(tmp_path), key_path, out)
    envelope = json.loads((out / "manifest.json").read_text())
    manifest = read_manifest(
        envelope, [public], today=date(2026, 11, 14), installed=0, app_version="0.1.0"
    )
    for part in ("image_model", "text_table"):
        entry = manifest[part]
        check_artefact(out / "artifacts" / "sha256" / entry["sha256"], entry)
    assert _private_key_text(key_path) not in caplog.text + (out / "manifest.json").read_text()


def test_publishing_is_refused_without_a_passing_parity_record(
    tmp_path: Path, key_path: Path
) -> None:
    tower, _ = write_artefacts(tmp_path / "artefacts")
    failing = parity_benchmark(tmp_path, tower, passed=False)
    out = tmp_path / "site"
    with pytest.raises(ParityRefused):
        publish(spec(tmp_path, benchmark=failing), key_path, out)
    assert not out.exists() or not any(out.iterdir()), "nothing is published"


def test_a_sequence_must_grow(tmp_path: Path, key_path: Path) -> None:
    out = tmp_path / "site"
    publish(spec(tmp_path, sequence=2), key_path, out)
    with pytest.raises(BundleRejected, match="sequence"):
        publish(spec(tmp_path, sequence=2), key_path, out)
    publish(spec(tmp_path, sequence=3), key_path, out)


def test_the_bundle_app_serves_the_manifest_and_immutable_artefacts(
    tmp_path: Path, key_path: Path
) -> None:
    out = tmp_path / "site"
    publish(spec(tmp_path), key_path, out)
    client = TestClient(create_app(out))
    manifest = client.get("/bundles/manifest.json")
    assert manifest.status_code == 200
    assert "no-cache" in manifest.headers["cache-control"]
    entry = json.loads((out / "manifest.json").read_text())
    tower = next((out / "artifacts" / "sha256").iterdir())
    served = client.get(f"/bundles/artifacts/sha256/{tower.name}")
    assert served.content == tower.read_bytes()
    assert "immutable" in served.headers["cache-control"]
    assert client.get("/bundles/artifacts/sha256/..%2Fmanifest.json").status_code == 404
    assert client.get(f"/bundles/artifacts/sha256/{'0' * 64}").status_code == 404
    assert entry["payloadType"]


def test_the_cli_publishes_a_spec_with_relative_paths_and_verifies_it(
    tmp_path: Path, key_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    bundle = spec(tmp_path, expires="2999-01-01")
    folder = Path(bundle.text_table).parent
    raw = bundle.model_dump(mode="json")
    raw["text_table"] = Path(bundle.text_table).name
    raw["image_model"]["path"] = Path(bundle.image_model.path).name
    raw["image_model"]["parity"]["benchmark"] = "../parity.json"
    (folder / "bundle.json").write_text(json.dumps(raw))
    out = tmp_path / "site"
    main(
        [
            "publish",
            "--spec",
            str(folder / "bundle.json"),
            "--key",
            str(key_path),
            "--out",
            str(out),
        ]
    )
    public = capsys.readouterr().out.split()[-1]
    main(["verify", "--out", str(out), "--public-key", public])
    assert "verified" in capsys.readouterr().out
    with pytest.raises(SystemExit, match="signature"):
        main(
            [
                "verify",
                "--out",
                str(out),
                "--public-key",
                public_key_text(Ed25519PrivateKey.generate()),
            ]
        )


def test_only_one_publish_runs_on_a_tree_at_a_time(tmp_path: Path, key_path: Path) -> None:
    out = tmp_path / "site"
    with lock(out), pytest.raises(BundleRejected, match="in progress"):
        publish(spec(tmp_path), key_path, out)
    publish(spec(tmp_path), key_path, out)
