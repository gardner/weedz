"""Audition presets are distinct and output planning refuses accidental replacement."""

import importlib.util
import json
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location(
    "music_batch", Path(__file__).parents[1] / "tools/demo-music/main.py"
)
assert spec and spec.loader
music = importlib.util.module_from_spec(spec)
spec.loader.exec_module(music)
PRESETS = Path(__file__).parents[1] / "tools/demo-music/auditions.json"


def test_ten_original_presets_have_distinct_seeds_prompts_and_percussion_options() -> None:
    presets = music.load_presets(PRESETS)
    assert len(presets) == 10
    assert len({item["seed"] for item in presets}) == 10
    assert len({item["prompt"] for item in presets}) == 10
    assert presets[6]["percussion"] and presets[9]["percussion"]


@pytest.mark.parametrize(
    "change", ["duplicate_seed", "duplicate_name", "invalid_name", "empty_prompt"]
)
def test_invalid_presets_fail_before_loading_a_model(tmp_path: Path, change: str) -> None:
    presets = json.loads(PRESETS.read_text())
    if change == "duplicate_seed":
        presets[1]["seed"] = presets[0]["seed"]
    elif change == "duplicate_name":
        presets[1]["name"] = presets[0]["name"]
    elif change == "invalid_name":
        presets[0]["name"] = "../escape"
    else:
        presets[0]["prompt"] = ""
    path = tmp_path / "presets.json"
    path.write_text(json.dumps(presets))
    with pytest.raises(ValueError):
        music.load_presets(path)
