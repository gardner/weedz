"""The film edit must preserve raw narration and never truncate a sentence."""

import importlib.util
import json
import wave
from pathlib import Path

import pytest

MODULE = Path(__file__).resolve().parents[1] / "tools/demo-video/demo_timeline.py"
spec = importlib.util.spec_from_file_location("demo_timeline", MODULE)
assert spec is not None and spec.loader is not None
timeline = importlib.util.module_from_spec(spec)
spec.loader.exec_module(timeline)


def raw_audio(path: Path) -> bytes:
    samples = bytes(range(256)) * 20
    with wave.open(str(path), "wb") as output:
        output.setparams((1, 2, 24000, 0, "NONE", "not compressed"))
        output.writeframes(samples)
    return samples


def test_narration_edit_preserves_every_sample_and_adds_only_silence(tmp_path: Path) -> None:
    samples = raw_audio(tmp_path / "breeze-intro-v1.wav")
    script = tmp_path / "script.json"
    script.write_text(json.dumps({"scenes": [{"id": "intro", "start": 0, "end": 2}]}))
    scenes = timeline.load_timeline(script, tmp_path)
    output = tmp_path / "master.wav"
    timeline.narration_master(scenes, output)
    with wave.open(str(output)) as master:
        assert master.getnframes() == 48000
        edited = master.readframes(master.getnframes())
    offset = round(0.6 * 24000) * 2
    assert edited[:offset] == bytes(offset)
    assert edited[offset : offset + len(samples)] == samples
    assert edited[offset + len(samples) :] == bytes(len(edited) - offset - len(samples))


def test_overlong_speech_is_refused_instead_of_cut_or_sped_up(tmp_path: Path) -> None:
    raw_audio(tmp_path / "breeze-intro-v1.wav")
    script = tmp_path / "script.json"
    script.write_text(json.dumps({"scenes": [{"id": "intro", "start": 0, "end": 0.65}]}))
    with pytest.raises(ValueError, match="Speech does not fit"):
        timeline.load_timeline(script, tmp_path)
