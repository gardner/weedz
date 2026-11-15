"""Website-only V3 footage cannot silently become blank or a repeated prior frame."""

import importlib
import subprocess
import sys
from pathlib import Path

import pytest
from PIL import Image

sys.path.insert(0, str(Path(__file__).parents[1] / "tools/demo-video"))


def test_v3_rejects_a_short_pipeline_capture(monkeypatch, tmp_path):
    module = importlib.import_module("web_demo_frames")
    original = subprocess.Popen

    def short_capture(_command, **kwargs):
        return original(
            [sys.executable, "-c", "import sys; sys.stdout.buffer.write(b'short')"], **kwargs
        )

    monkeypatch.setattr(subprocess, "Popen", short_capture)
    frames = module.WebsiteFrames.__new__(module.WebsiteFrames)
    frames.pipeline = tmp_path
    frames.ffmpeg = Path("unused")
    frames.pipeline_decoder = None
    frames.last_pipeline = None
    monkeypatch.setattr(frames, "base", lambda _: Image.new("RGB", (1920, 1080)))
    try:
        with pytest.raises(RuntimeError, match="ended early"):
            frames.review(0)
    finally:
        if frames.pipeline_decoder is not None:
            decoder = frames.pipeline_decoder
            process = getattr(decoder, "process", decoder)
            assert process is not None
            if process.stdout is not None:
                process.stdout.close()
            process.wait(timeout=10)
