"""Generated media cannot escape the output policy through paths or sidecar links."""

import importlib.util
import subprocess
from pathlib import Path

import pytest

SPEC = importlib.util.spec_from_file_location(
    "demo_paths", Path(__file__).parents[1] / "scripts/demo_paths.py"
)
assert SPEC is not None and SPEC.loader is not None
paths = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(paths)


def repository(path: Path) -> Path:
    subprocess.run(["git", "init", "--quiet", str(path)], check=True)
    return path


def test_nested_generated_path_inside_any_worktree_is_refused(tmp_path: Path) -> None:
    repo = repository(tmp_path / "another repository")
    with pytest.raises(ValueError, match="outside every git worktree"):
        paths.outside_git(repo / "not-created/yet/demo.mp4")
    assert not (repo / "not-created").exists()


def test_alias_into_a_repository_cannot_hide_a_generated_destination(tmp_path: Path) -> None:
    repo = repository(tmp_path / "repo")
    alias = tmp_path / "looks-external"
    alias.symlink_to(repo, target_is_directory=True)
    with pytest.raises(ValueError, match="outside every git worktree"):
        paths.outside_git(alias / "new/subdirectory/voice.wav")


def test_linked_worktree_git_file_is_detected(tmp_path: Path) -> None:
    linked = tmp_path / "linked"
    linked.mkdir()
    (linked / ".git").write_text(f"gitdir: {repository(tmp_path / 'repo') / '.git'}\n")
    with pytest.raises(ValueError, match="outside every git worktree"):
        paths.outside_git(linked / "capture.png")


def test_external_parent_alias_returns_real_path_for_every_writer(tmp_path: Path) -> None:
    external = tmp_path / "actual media"
    external.mkdir()
    repo = repository(tmp_path / "repo")
    alias = repo / "outside-media"
    alias.symlink_to(external, target_is_directory=True)
    assert paths.outside_git(alias / "new/voice.wav") == external / "new/voice.wav"


@pytest.mark.parametrize("suffix", [".wav", ".json", ".png"])
def test_existing_primary_or_sidecar_is_preserved(tmp_path: Path, suffix: str) -> None:
    output = tmp_path / "new.wav"
    previous = output.with_suffix(suffix)
    previous.write_text("existing artifact")
    with pytest.raises(ValueError, match="already exists"):
        paths.new_output(output, sidecars=(".json", ".png"))
    assert previous.read_text() == "existing artifact"


def test_broken_sidecar_symlink_is_not_followed_or_overwritten(tmp_path: Path) -> None:
    output = tmp_path / "narration.wav"
    repo = repository(tmp_path / "repo")
    sidecar = output.with_suffix(".json")
    sidecar.symlink_to(repo / "new-metadata.json")
    with pytest.raises(ValueError, match="already exists"):
        paths.new_output(output, sidecars=(".json",))
    assert sidecar.is_symlink()
    assert not (repo / "new-metadata.json").exists()
