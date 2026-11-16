"""The release command consumes a pinned reviewed manifest and an explicit policy."""

import hashlib
from pathlib import Path

import pytest
from test_gold_release import materialize, spec

from weedz.manifest import write_manifest
from weedz.release import read_release
from weedz.release_cli import main


def freeze_args(tmp_path: Path) -> list[str]:
    source = tmp_path / "reviewed"
    samples = materialize(source)
    manifest = source / "samples.jsonl"
    sha = write_manifest(manifest, samples)
    policy = tmp_path / "release-spec.json"
    policy.write_text(spec().model_dump_json())
    return [
        "freeze",
        "--manifest",
        str(manifest),
        "--manifest-sha256",
        sha,
        "--spec",
        str(policy),
        "--assets-root",
        str(source),
        "--output-dir",
        str(tmp_path / "release"),
    ]


def test_freeze_cli_writes_a_policy_checked_self_contained_release(tmp_path: Path, capsys):
    args = freeze_args(tmp_path)
    main(args)
    assert "checked-fixture" in capsys.readouterr().out
    record, samples = read_release(tmp_path / "release")
    assert record.review_policy == spec().review_policy
    assert record.assets and len(record.assets) == 3
    assert len(samples) == 3


def test_freeze_cli_refuses_changed_review_input_before_writing(tmp_path: Path, capsys):
    args = freeze_args(tmp_path)
    manifest = tmp_path / "reviewed/samples.jsonl"
    manifest.write_bytes(manifest.read_bytes() + b"\n")
    assert hashlib.sha256(manifest.read_bytes()).hexdigest() != args[4]
    with pytest.raises(SystemExit):
        main(args)
    assert "checksum mismatch" in capsys.readouterr().err
    assert not (tmp_path / "release").exists()
