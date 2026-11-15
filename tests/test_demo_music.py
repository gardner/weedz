"""Generation must not overwrite media or accidentally target another GPU."""

import importlib.util
import subprocess
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location(
    "demo_music", Path(__file__).parents[1] / "tools/demo-music/main.py"
)
assert spec and spec.loader
music = importlib.util.module_from_spec(spec)
spec.loader.exec_module(music)


def test_generation_refuses_invalid_duration_and_seed(tmp_path: Path) -> None:
    for seconds in (0, -1, float("nan"), float("inf"), 301):
        with pytest.raises(ValueError):
            music.validate_request(seconds, 112, tmp_path / "music.wav")
    with pytest.raises(ValueError):
        music.validate_request(180, -1, tmp_path / "music.wav")


def test_existing_audio_or_provenance_is_never_overwritten(tmp_path: Path) -> None:
    output = tmp_path / "music.wav"
    output.with_suffix(".json").write_text("existing provenance")
    with pytest.raises(FileExistsError):
        music.validate_request(180, 112, output)


def test_lyrics_contain_only_instrumental_structure_tags() -> None:
    assert all(line.startswith("[") and line.endswith("]") for line in music.LYRICS.splitlines())
    assert "vocal" not in music.LYRICS.lower()


def test_music_cannot_target_another_git_checkout(tmp_path: Path) -> None:
    checkout = tmp_path / "other-checkout"
    subprocess.run(["git", "init", "--quiet", str(checkout)], check=True)
    alias = tmp_path / "alias"
    alias.symlink_to(checkout, target_is_directory=True)
    with pytest.raises(ValueError, match="outside every git worktree"):
        music.validate_request(180, 112, alias / "score.wav")
