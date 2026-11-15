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


def test_empty_cache_can_fetch_only_the_pinned_snapshot_before_local_loading(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import sys
    from types import SimpleNamespace

    calls = []
    pipeline = SimpleNamespace(
        load_components=lambda **kwargs: calls.append(("components", kwargs)),
        to=lambda device: calls.append(("device", device)),
    )

    def snapshot(model, **kwargs):
        calls.append(("snapshot", model, kwargs))
        if kwargs.get("local_files_only"):
            raise RuntimeError("Pinned snapshot is not in this clean cache")
        return str(tmp_path)

    monkeypatch.setenv("CUDA_VISIBLE_DEVICES", "0")
    monkeypatch.setitem(
        sys.modules,
        "torch",
        SimpleNamespace(
            bfloat16="bfloat16",
            cuda=SimpleNamespace(
                is_available=lambda: True, mem_get_info=lambda: (30 * 1024**3, 32 * 1024**3)
            ),
        ),
    )
    monkeypatch.setitem(sys.modules, "huggingface_hub", SimpleNamespace(snapshot_download=snapshot))
    monkeypatch.setitem(
        sys.modules,
        "diffusers",
        SimpleNamespace(
            ModularPipeline=SimpleNamespace(
                from_pretrained=lambda path, **kwargs: (
                    calls.append(("from", path, kwargs)) or pipeline
                ),
            )
        ),
    )
    loaded, folder = music.load_pipeline()
    assert loaded is pipeline and folder == tmp_path
    assert calls[0][0:2] == ("snapshot", music.MODEL)
    assert calls[0][2]["revision"] == music.REVISION
    assert calls[0][2].get("local_files_only", False) is False
    assert calls[1] == ("from", str(tmp_path), {"local_files_only": True})
    assert calls[2] == ("components", {"dtype": "bfloat16", "local_files_only": True})
