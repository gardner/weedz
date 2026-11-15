"""Capture safety checks run before writes and survive optimized Python execution."""

import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[1]


def test_live_capture_rejects_output_inside_source_before_writing(tmp_path: Path) -> None:
    source = tmp_path / "public-pilot"
    source.mkdir()
    alias = tmp_path / "alias"
    alias.symlink_to(source, target_is_directory=True)
    output = alias / "new-capture"
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/capture_live_flutter.py"),
            "--output",
            str(output),
            "--source-pilot",
            str(source),
            "--ffmpeg",
            "missing",
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    assert "independent" in result.stderr
    assert not output.exists()


@pytest.mark.parametrize("active,crops", [(1, 0), (0, 1), (0, 0)])
def test_erasure_validation_survives_optimized_python(
    tmp_path: Path, active: int, crops: int
) -> None:
    reports = tmp_path / "intake/reports"
    images = reports / "images"
    images.mkdir(parents=True)
    with sqlite3.connect(reports / "reports.sqlite3") as db:
        db.execute("CREATE TABLE reports(body TEXT)")
        if active:
            db.execute("INSERT INTO reports VALUES ('retained report')")
    if crops:
        (images / "retained.jpg").write_bytes(b"retained crop")
    code = (
        "import sys; from pathlib import Path; "
        f"sys.path.insert(0, {str(ROOT / 'scripts')!r}); "
        "from capture_live_flutter import verify_erasure; "
        f"print(verify_erasure(Path({str(tmp_path)!r})))"
    )
    result = subprocess.run([sys.executable, "-O", "-c", code], capture_output=True, text=True)
    if active or crops:
        assert result.returncode != 0
        assert "Erasure verification failed" in result.stderr
    else:
        assert result.returncode == 0, result.stderr
        assert "(0, 0)" in result.stdout


def test_review_capture_rejects_output_inside_snapshot_before_writing(tmp_path: Path) -> None:
    source = tmp_path / "snapshot"
    source.mkdir()
    alias = tmp_path / "snapshot-alias"
    alias.symlink_to(source, target_is_directory=True)
    output = alias / "images/new-capture"
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/capture_review_demo.py"),
            "--snapshot",
            str(source),
            "--output",
            str(output),
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    assert "independent" in result.stderr
    assert not output.exists()
    assert list(source.iterdir()) == []
