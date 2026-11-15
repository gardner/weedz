"""Transcript scene identity is explicit; captions never infer it from list position."""

import importlib
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parents[1] / "tools/demo-video"))


@pytest.mark.parametrize(
    "scene",
    [
        {"segments": []},
        {"scene": "scene-01", "file": "scene-01.wav", "segments": []},
        {"scene": True, "file": "scene-01.wav", "segments": []},
        {"scene": 1, "file": "", "segments": []},
    ],
)
def test_missing_or_invalid_scene_identity_has_a_readable_error(scene):
    helper = importlib.import_module("demo_transcript")
    with pytest.raises(ValueError, match="scene.*file"):
        helper.flatten_transcript({"scenes": [scene]})


def test_duplicate_scene_numbers_are_rejected_and_valid_words_are_preserved():
    helper = importlib.import_module("demo_transcript")
    word = {"word": "Help", "start": 0.1, "end": 0.4}
    scene = {"scene": 1, "file": "selected-take.wav", "segments": [{"words": [word]}]}
    assert helper.flatten_transcript({"scenes": [scene]}) == [
        {"scene": 1, "file": "selected-take.wav", "words": [word]}
    ]
    with pytest.raises(ValueError, match="scene.*file"):
        helper.flatten_transcript({"scenes": [scene, scene]})
