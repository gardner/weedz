"""Build a timed, sample-preserving narration master and readable captions."""

import hashlib
import io
import json
import re
import sys
import wave
from difflib import SequenceMatcher
from pathlib import Path, PureWindowsPath
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
from demo_voice import verified_narration  # noqa: E402


def load_timeline(script: Path, audio: Path) -> list[dict[str, Any]]:
    scenes = json.loads(script.read_text())["scenes"]
    previous_end = 0
    for index, scene in enumerate(scenes):
        filename = "breeze-intro-v1.wav" if index == 0 else f"scene-{index + 1:02}-raw-v3.wav"
        filename = scene.get("audio_file", filename)
        scene["audio"] = str(audio / filename)
        raw, provenance = verified_narration(Path(scene["audio"]), scene["narration"])
        scene["audio_sha256"] = provenance["wav_sha256"]
        scene["narration_provenance"] = provenance
        with wave.open(io.BytesIO(raw)) as source:
            if (source.getnchannels(), source.getsampwidth(), source.getframerate()) != (
                1,
                2,
                24000,
            ):
                raise ValueError("Expected native Breeze mono PCM16 / 24 kHz")
            scene["speech_duration"] = source.getnframes() / source.getframerate()
        scene["speech_start"] = scene["start"] + 0.6
        if scene["start"] != previous_end:
            raise ValueError("Visual scenes must be contiguous")
        if scene["speech_start"] + scene["speech_duration"] > scene["end"]:
            raise ValueError(f"Speech does not fit {scene['id']}; extend the scene")
        previous_end = scene["end"]
    return scenes


def portable_timeline(scenes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Keep local input paths for reading; publish only stable narration basenames."""
    delivered = []
    for scene in scenes:
        entry = dict(scene, audio=PureWindowsPath(scene["audio"]).name)
        if "audio_file" in entry:
            entry["audio_file"] = PureWindowsPath(entry["audio_file"]).name
        delivered.append(entry)
    return delivered


def narration_master(scenes: list[dict[str, Any]], output: Path) -> None:
    """Insert silence between utterances; retain every source PCM sample unchanged."""
    master = bytearray(int(scenes[-1]["end"] * 24000) * 2)
    for scene in scenes:
        raw, _ = verified_narration(Path(scene["audio"]), scene["narration"])
        if hashlib.sha256(raw).hexdigest() != scene["audio_sha256"]:
            raise ValueError("Breeze provenance changed after timeline validation")
        with wave.open(io.BytesIO(raw)) as source:
            frames = source.readframes(source.getnframes())
        offset = round(scene["speech_start"] * 24000) * 2
        master[offset : offset + len(frames)] = frames
    with wave.open(str(output), "wb") as destination:
        destination.setparams((1, 2, 24000, 0, "NONE", "not compressed"))
        destination.writeframes(master)


def normal(word: str) -> str:
    return re.sub(r"\W", "", word.lower())


def word_times(words: list[str], spoken: dict[str, Any], duration: float) -> dict[int, float]:
    """Interpolate unmatched canonical words between measured ASR anchors."""
    times: dict[int, float] = {0: 0.0, len(words): duration}
    matcher = SequenceMatcher(
        None, [normal(word) for word in words], [normal(w["word"]) for w in spoken["words"]]
    )
    for block in matcher.get_matching_blocks():
        for offset in range(block.size):
            times[block.a + offset] = spoken["words"][block.b + offset]["start"]
    anchors = sorted(times)
    for left, right in zip(anchors, anchors[1:], strict=False):
        for index in range(left + 1, right):
            times[index] = times[left] + (times[right] - times[left]) * (index - left) / (
                right - left
            )
    return times


def caption_cues(scenes: list[dict[str, Any]], transcript: Path) -> list[dict[str, Any]]:
    """Align canonical spelling to measured ASR word times."""
    measured = json.loads(transcript.read_text())
    cues = []
    for index, (scene, spoken) in enumerate(zip(scenes, measured, strict=True), 1):
        source_file = Path(str(spoken.get("file", "")).replace("\\", "/")).name
        if spoken.get("scene") != index or source_file != Path(scene["audio"]).name:
            raise ValueError(f"Transcript identity does not match {scene['id']}")
        words = scene["narration"].replace("—", " — ").split()
        times = word_times(words, spoken, scene["speech_duration"])
        start = 0
        while start < len(words):
            end = start + 1
            while end < len(words) and len(" ".join(words[start : end + 1])) <= 82:
                if end - start >= 5 and words[end - 1].endswith((".", "?", ";")):
                    break
                end += 1
            cues.append(
                {
                    "start": scene["speech_start"] + times[start],
                    "end": scene["speech_start"] + times[end],
                    "text": " ".join(words[start:end]).replace(" — ", "—"),
                }
            )
            start = end
    return cues


def srt(cues: list[dict[str, Any]]) -> str:
    def timestamp(seconds: float) -> str:
        milliseconds = round(seconds * 1000)
        hours, milliseconds = divmod(milliseconds, 3600000)
        minutes, milliseconds = divmod(milliseconds, 60000)
        seconds, milliseconds = divmod(milliseconds, 1000)
        return f"{hours:02}:{minutes:02}:{seconds:02},{milliseconds:03}"

    return (
        "\n\n".join(
            f"{index}\n{timestamp(cue['start'])} --> {timestamp(cue['end'])}\n{cue['text']}"
            for index, cue in enumerate(cues, 1)
        )
        + "\n"
    )
