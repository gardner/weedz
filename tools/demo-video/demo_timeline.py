"""Build a timed, sample-preserving narration master and readable captions."""

import json
import re
import wave
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any


def load_timeline(script: Path, audio: Path) -> list[dict[str, Any]]:
    scenes = json.loads(script.read_text())["scenes"]
    previous_end = 0
    for index, scene in enumerate(scenes):
        filename = "breeze-intro-v1.wav" if index == 0 else f"scene-{index + 1:02}-raw-v3.wav"
        filename = scene.get("audio_file", filename)
        scene["audio"] = str(audio / filename)
        with wave.open(scene["audio"]) as source:
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


def narration_master(scenes: list[dict[str, Any]], output: Path) -> None:
    """Insert silence between utterances; retain every source PCM sample unchanged."""
    master = bytearray(int(scenes[-1]["end"] * 24000) * 2)
    for scene in scenes:
        with wave.open(scene["audio"]) as source:
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
    for scene, spoken in zip(scenes, measured, strict=True):
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
