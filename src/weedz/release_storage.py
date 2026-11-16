"""Publish a complete, durable release directory with one atomic rename."""

import os
import shutil
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path


def sync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _sync_tree(path: Path) -> None:
    for child in path.iterdir():
        if child.is_dir():
            _sync_tree(child)
        else:
            with child.open("rb") as stream:
                os.fsync(stream.fileno())
    sync_directory(path)


def require_empty(directory: Path) -> None:
    if directory.is_symlink() or (
        directory.exists() and (not directory.is_dir() or any(directory.iterdir()))
    ):
        raise ValueError(f"Release directory must be empty: {directory}")


def require_asset_destination(directory: Path) -> None:
    resolved = directory.resolve()
    if any((parent / ".git").exists() for parent in (resolved, *resolved.parents)):
        raise ValueError("Materialized release images and masks must stay outside Git")


@contextmanager
def staged_release(directory: Path, *, private: bool = True) -> Iterator[Path]:
    """Keep interrupted writes private; POSIX rename also replaces an empty directory."""
    require_empty(directory)
    directory.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=f".{directory.name}-pending-", dir=directory.parent))
    try:
        yield staging
        _sync_tree(staging)
        require_empty(directory)
        _publication_metadata(staging, directory, private=private)
        sync_directory(staging)
        os.rename(staging, directory)
        sync_directory(directory.parent)
    finally:
        if staging.exists():
            shutil.rmtree(staging)


def _publication_metadata(staging: Path, directory: Path, *, private: bool) -> None:
    if directory.exists():
        # Rename replaces the empty inode; retain the caller's explicit sharing
        # permissions, group and supported extended metadata (including POSIX ACLs).
        if staging.stat().st_gid != directory.stat().st_gid:
            os.chown(staging, -1, directory.stat().st_gid)
        shutil.copystat(directory, staging, follow_symlinks=False)
    elif not private:
        # A normal mkdir observes the actual umask/default ACL without reading or
        # changing the process-wide umask. Its parent remains private throughout.
        template = staging / ".publication-permissions"
        template.mkdir()
        shutil.copystat(template, staging, follow_symlinks=False)
        template.rmdir()
