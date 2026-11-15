"""The documented capture launcher preserves files and caller-resolved paths."""

import importlib.util
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parents[1]


def test_existing_capture_is_never_overwritten(tmp_path):
    output = tmp_path / "completed-capture"
    output.mkdir()
    original = output / "source-reference.png"
    original.write_bytes(b"original immutable capture")
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/capture_segmentation_ui.py"),
            "--output",
            str(output),
            "--ffmpeg",
            "unused",
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    assert original.read_bytes() == b"original immutable capture"
    assert list(output.iterdir()) == [original]


def test_launcher_runs_the_project_from_a_foreign_cwd(tmp_path, monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT / "scripts"))
    spec = importlib.util.spec_from_file_location(
        "segmentation_launcher", ROOT / "scripts/capture_segmentation_ui.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(module, "outside_git", lambda path: path.resolve())
    monkeypatch.setattr(sys, "argv", ["capture", "--output", "out", "--ffmpeg", "local-ffmpeg"])
    calls = []
    monkeypatch.setattr(
        module.subprocess, "run", lambda command, **kwargs: calls.append((command, kwargs))
    )
    module.main()
    assert calls[0][1]["cwd"] == ROOT
    assert calls[0][1]["env"]["WEEDZ_CAPTURE_DIR"] == str(tmp_path / "out")
    assert calls[0][1]["env"]["WEEDZ_FFMPEG"] == str(tmp_path / "local-ffmpeg")
