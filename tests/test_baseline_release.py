"""The Leafy Spurge baseline split, reproduced as a frozen release."""

import json
from pathlib import Path

import pytest

from weedz import cli
from weedz.adapters import leafy_spurge_samples
from weedz.baseline_release import (
    leafy_spurge_spec,
    partition_mismatches,
    write_leafy_spurge_release,
)
from weedz.dataset import read_observations
from weedz.partition import partition_observations
from weedz.provenance import record_dataset
from weedz.release import read_release

WHEN = "2026-11-14T00:00:00+00:00"


def recorded_partitions(dataset_dir: Path) -> dict[str, list[int]]:
    partitions = partition_observations(read_observations(dataset_dir))
    return {name: [row.sample_id for row in rows] for name, rows in partitions.items().items()}


def test_the_baseline_release_reproduces_the_pipeline_partitions(
    dataset_dir: Path, tmp_path: Path
) -> None:
    record_dataset(dataset_dir)
    release = write_leafy_spurge_release(dataset_dir, tmp_path / "release", recorded_at=WHEN)
    assert partition_mismatches(release, recorded_partitions(dataset_dir)) == {}
    assert release.splits["validation"].groups == ["2"]
    assert release.splits["test"].groups == ["3"]
    assert release.buffer is not None and release.buffer.distance_m == 2.0
    # The baseline's test has been reported, so it is not a fresh holdout.
    assert release.test_status == "inspected"
    assert read_release(tmp_path / "release")[0] == release


def test_a_differing_recorded_partition_is_reported(dataset_dir: Path, tmp_path: Path) -> None:
    record_dataset(dataset_dir)
    release = write_leafy_spurge_release(dataset_dir, tmp_path / "release", recorded_at=WHEN)
    recorded = {"fit": [], "validation": [200], "test": [300, 999], "excluded": []}
    mismatches = partition_mismatches(release, recorded)
    assert set(mismatches) == {"fit", "validation", "test"}
    assert mismatches["test"]["only_recorded"] == ["leafy-spurge:999"]
    assert "leafy-spurge:301" in mismatches["test"]["only_release"]


def test_published_train_and_test_sharing_a_cluster_is_refused(dataset_dir: Path) -> None:
    record_dataset(dataset_dir)
    samples = leafy_spurge_samples(dataset_dir)
    groups = {"survey_cluster": "3", "source_split": "train"}
    leaked = samples[0].model_copy(update={"groups": groups})
    with pytest.raises(ValueError, match="share a survey cluster"):
        leafy_spurge_spec([leaked, *samples[1:]])


def run_cli(monkeypatch: pytest.MonkeyPatch, *args: str) -> None:
    monkeypatch.setattr("sys.argv", ["weedz", "release", *args])
    cli.main()


def test_cli_builds_checks_and_advances_a_release(
    dataset_dir: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    record_dataset(dataset_dir)
    run = tmp_path / "run.json"
    run.write_text(json.dumps({"partitions": recorded_partitions(dataset_dir)}))
    output = tmp_path / "release"
    run_cli(
        monkeypatch,
        "leafy-spurge",
        "--data-dir",
        str(dataset_dir),
        "--output-dir",
        str(output),
        "--check-run",
        str(run),
    )
    printed = capsys.readouterr().out
    assert "match the recorded run" in printed and "fit 24" in printed and "inspected" in printed
    run_cli(monkeypatch, "status", str(output), "used_for_selection", "--note", "tuned")
    run_cli(monkeypatch, "verify", str(output))
    assert "used_for_selection" in capsys.readouterr().out
    assert read_release(output)[0].test_status == "used_for_selection"


def test_cli_fails_when_the_recorded_run_differs(
    dataset_dir: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    record_dataset(dataset_dir)
    run = tmp_path / "run.json"
    run.write_text(json.dumps({"partitions": {"fit": [], "validation": [], "test": [0]}}))
    with pytest.raises(SystemExit) as error:
        run_cli(
            monkeypatch,
            "leafy-spurge",
            "--data-dir",
            str(dataset_dir),
            "--output-dir",
            str(tmp_path / "release"),
            "--check-run",
            str(run),
        )
    assert error.value.code == 1
    assert "differs" in capsys.readouterr().err


def test_cli_reports_a_refused_status_change_without_a_traceback(
    dataset_dir: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    record_dataset(dataset_dir)
    output = tmp_path / "release"
    write_leafy_spurge_release(dataset_dir, output, recorded_at=WHEN)
    with pytest.raises(SystemExit) as error:
        run_cli(monkeypatch, "status", str(output), "fresh", "--note", "reset")
    assert error.value.code == 1
    assert "cannot return from inspected to fresh" in capsys.readouterr().err
