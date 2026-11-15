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


@pytest.mark.parametrize(
    "identity",
    [
        {"scene": 2, "file": "selected.wav"},
        {"scene": 1, "file": "older-take.wav"},
    ],
)
def test_caption_alignment_refuses_a_different_passage(
    tmp_path: Path, identity: dict[str, object]
) -> None:
    transcript = tmp_path / "transcript.json"
    transcript.write_text(json.dumps([{**identity, "words": [{"word": "Hello", "start": 0.1}]}]))
    scenes = [
        {
            "id": "scene-01",
            "audio": str(tmp_path / "selected.wav"),
            "narration": "Hello",
            "speech_duration": 1,
            "speech_start": 0.6,
        }
    ]
    with pytest.raises(ValueError, match="Transcript identity"):
        timeline.caption_cues(scenes, transcript)


def test_caption_identity_accepts_the_selected_filename_from_another_machine(
    tmp_path: Path,
) -> None:
    transcript = tmp_path / "transcript.json"
    transcript.write_text(
        json.dumps(
            [
                {
                    "scene": 1,
                    "file": "C:\\recording\\selected.wav",
                    "words": [{"word": "Hello", "start": 0.1}],
                }
            ]
        )
    )
    scenes = [
        {
            "id": "scene-01",
            "audio": str(tmp_path / "selected.wav"),
            "narration": "Hello",
            "speech_duration": 1,
            "speech_start": 0.6,
        }
    ]
    assert timeline.caption_cues(scenes, transcript)[0]["text"] == "Hello"


def test_delivered_timeline_is_portable_without_changing_runtime_audio_paths(
    tmp_path: Path,
) -> None:
    scenes = [
        {
            "id": "scene-01",
            "audio": str(tmp_path / "voice.wav"),
            "audio_file": str(tmp_path / "voice.wav"),
            "narration": "Hello",
        }
    ]
    delivered = timeline.portable_timeline(scenes)
    assert delivered[0]["audio"] == "voice.wav"
    assert delivered[0]["audio_file"] == "voice.wav"
    assert str(tmp_path) not in json.dumps(delivered)
    assert scenes[0]["audio"] == str(tmp_path / "voice.wav")
