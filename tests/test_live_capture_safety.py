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


@pytest.mark.parametrize("times_out", [False, True])
def test_owned_server_is_reaped_even_if_graceful_shutdown_times_out(monkeypatch, times_out):
    import importlib
    import signal
    from types import SimpleNamespace

    monkeypatch.syspath_prepend(str(ROOT / "scripts"))
    module = importlib.import_module("capture_live_flutter")
    signals, waits = [], []

    def wait(timeout):
        waits.append(timeout)
        if times_out and len(waits) == 1:
            raise subprocess.TimeoutExpired("owned-server", timeout)
        return 0

    monkeypatch.setattr(module.os, "killpg", lambda pid, sig: signals.append((pid, sig)))
    module.stop_server(SimpleNamespace(pid=123, poll=lambda: None, wait=wait))
    assert signals == [(123, signal.SIGTERM)] + ([(123, signal.SIGKILL)] if times_out else [])
    assert waits == ([10, 10] if times_out else [10])


@pytest.mark.parametrize(
    "script,source_flag,extra",
    [
        ("capture_live_flutter", "--source-pilot", ["--ffmpeg", "unused"]),
        ("capture_review_demo", "--snapshot", []),
    ],
)
def test_child_receives_the_checked_absolute_source_from_another_cwd(
    tmp_path, monkeypatch, script, source_flag, extra
):
    import importlib

    monkeypatch.syspath_prepend(str(ROOT / "scripts"))
    module = importlib.import_module(script)
    monkeypatch.chdir(tmp_path)
    source = tmp_path / "relative-source"
    source.mkdir()
    monkeypatch.setattr(module, "outside_git", lambda path: path.resolve(), raising=False)
    monkeypatch.setattr(module, "new_output", lambda path: path.resolve(), raising=False)
    if script == "capture_review_demo":
        ports = iter([8311, 8312])
        monkeypatch.setattr(module, "available_port", lambda: next(ports))
    commands = []

    class StopBeforeLaunching(Exception):
        pass

    def launch(command, **_kwargs):
        commands.append(command)
        raise StopBeforeLaunching

    monkeypatch.setattr(module.subprocess, "Popen", launch)
    monkeypatch.setattr(
        sys, "argv", [script, source_flag, "relative-source", "--output", "out", *extra]
    )
    with pytest.raises(StopBeforeLaunching):
        module.main()
    index = commands[0].index(source_flag)
    assert commands[0][index + 1] == str(source)
