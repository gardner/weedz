"""Resolve generated-demo paths and keep every artifact outside Git worktrees."""

import subprocess
from pathlib import Path


def outside_git(path: Path) -> Path:
    """Return the real destination, rejecting worktrees through symlinks too."""
    resolved = path.resolve()
    parent = resolved if resolved.is_dir() else resolved.parent
    while not parent.exists():
        parent = parent.parent
    found = subprocess.run(
        ["git", "-C", str(parent), "rev-parse", "--is-inside-work-tree"],
        capture_output=True,
        text=True,
        check=False,
    )
    if found.returncode == 0:
        raise ValueError("Demo artifacts must be outside every git worktree")
    if "not a git repository" not in found.stderr:
        raise ValueError("Could not verify that the demo destination is outside Git")
    return resolved


def new_output(path: Path, *, sidecars: tuple[str, ...] = ()) -> Path:
    """Reserve a new artifact name without overwriting outputs or their sidecars.

    This validates destinations before generation; callers still own writing them.
    Existing symlinks count as existing artifacts even when their targets are absent.
    """
    candidates = (path, *(path.with_suffix(suffix) for suffix in sidecars))
    for candidate in candidates:
        if candidate.exists() or candidate.is_symlink():
            raise ValueError(f"Choose a new output name; an artifact already exists: {candidate}")
        outside_git(candidate)
    return outside_git(path)
