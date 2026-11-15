"""Generation receipts identify the exact native file, without processing its samples."""

import hashlib
import importlib.util
import json
import sys
import wave
from pathlib import Path


def test_breeze_generation_records_the_exact_native_wav_hash(tmp_path, monkeypatch):
    root = Path(__file__).parents[1]
    spec = importlib.util.spec_from_file_location("demo_audio", root / "tools/demo-audio/main.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    output = tmp_path / "voice.wav"
    passage = tmp_path / "passage.txt"
    passage.write_text("Hello")
    reference = tmp_path / "reference.wav"
    reference.write_bytes(b"native-reference-bytes")
    reference_text = tmp_path / "reference.txt"
    reference_text.write_text("Reference words")
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "audio",
            "--source",
            str(tmp_path),
            "--model",
            str(tmp_path / "model"),
            "--text-file",
            str(passage),
            "--reference-audio",
            str(reference),
            "--reference-text-file",
            str(reference_text),
            "--output",
            str(output),
        ],
    )
    monkeypatch.setattr(
        module.subprocess, "check_output", lambda *_args, **_kwargs: module.SOURCE_REVISION
    )
    monkeypatch.setattr(module.importlib.metadata, "version", lambda _: "test-version")
    monkeypatch.setattr(module, "new_output", lambda path, **_kwargs: path.resolve())

    def generate(_command, **_kwargs):
        with wave.open(str(output), "wb") as generated:
            generated.setparams((1, 2, 24000, 0, "NONE", "not compressed"))
            generated.writeframes(b"\x01\x00" * 240)

    monkeypatch.setattr(module.subprocess, "run", generate)
    module.main()
    proof = json.loads(output.with_suffix(".json").read_text())
    assert proof["wav_sha256"] == hashlib.sha256(output.read_bytes()).hexdigest()
    assert proof["text"] == "Hello"
    assert proof["model"] == "BreezeBlue/Breeze-TTS-2"

    assert "checkpoint_path" not in proof
    assert proof["reference_audio"] == reference.name
    assert proof["reference_audio_sha256"] == hashlib.sha256(reference.read_bytes()).hexdigest()
