"""The film edit must preserve raw narration and never truncate a sentence."""

import hashlib
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
    path.with_suffix(".json").write_text(
        json.dumps(
            {
                "model": "BreezeBlue/Breeze-TTS-2",
                "expected_model_revision": "3e28c5151381a722f1d8661b4118c298caa77aa4",
                "source_revision": "daa6cb2efe5471f09369229f322d20bb956cb3c3",
                "wav_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "text": "Hello",
            }
        )
    )
    return samples


def test_narration_edit_preserves_every_sample_and_adds_only_silence(tmp_path: Path) -> None:
    samples = raw_audio(tmp_path / "breeze-intro-v1.wav")
    script = tmp_path / "script.json"
    script.write_text(
        json.dumps({"scenes": [{"id": "intro", "start": 0, "end": 2, "narration": "Hello"}]})
    )
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
    script.write_text(
        json.dumps({"scenes": [{"id": "intro", "start": 0, "end": 0.65, "narration": "Hello"}]})
    )
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


def test_narration_without_generation_receipt_cannot_inherit_breeze_provenance(tmp_path):
    raw_audio(tmp_path / "breeze-intro-v1.wav")
    script = tmp_path / "script.json"
    script.write_text(
        json.dumps({"scenes": [{"id": "intro", "start": 0, "end": 2, "narration": "Hello"}]})
    )
    (tmp_path / "breeze-intro-v1.json").unlink()
    with pytest.raises(ValueError, match="Breeze provenance"):
        timeline.load_timeline(script, tmp_path)


@pytest.mark.parametrize(
    "change", [{"model": "Other model"}, {"wav_sha256": "0" * 64}, {"text": "Other passage"}]
)
def test_narration_identity_mismatch_is_not_accepted(tmp_path, change):
    path = tmp_path / "breeze-intro-v1.wav"
    raw_audio(path)
    sidecar = path.with_suffix(".json")
    sidecar.write_text(json.dumps(json.loads(sidecar.read_text()) | change))
    script = tmp_path / "script.json"
    script.write_text(
        json.dumps({"scenes": [{"id": "intro", "start": 0, "end": 2, "narration": "Hello"}]})
    )
    with pytest.raises(ValueError, match="Breeze provenance"):
        timeline.load_timeline(script, tmp_path)


@pytest.mark.parametrize("update_receipt", [False, True])
def test_replaced_native_wav_is_rechecked_before_pcm_assembly(tmp_path, update_receipt):
    path = tmp_path / "breeze-intro-v1.wav"
    samples = raw_audio(path)
    script = tmp_path / "script.json"
    script.write_text(
        json.dumps({"scenes": [{"id": "intro", "start": 0, "end": 2, "narration": "Hello"}]})
    )
    scenes = timeline.load_timeline(script, tmp_path)
    with wave.open(str(path), "wb") as output:
        output.setparams((1, 2, 24000, 0, "NONE", "not compressed"))
        output.writeframes(bytes(len(samples)))
    if update_receipt:
        sidecar = path.with_suffix(".json")
        proof = json.loads(sidecar.read_text())
        sidecar.write_text(
            json.dumps(proof | {"wav_sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
        )
    with pytest.raises(ValueError, match="Breeze provenance"):
        timeline.narration_master(scenes, tmp_path / "master.wav")
    assert not (tmp_path / "master.wav").exists()
