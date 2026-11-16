"""Bounded labelled-source archives never extract publisher paths."""

import hashlib
import zipfile
from pathlib import Path

import pytest

from weedz.labelled.archive import SourceArchive


def archive(tmp_path: Path, entries: list[tuple[str, bytes]]) -> tuple[Path, str]:
    path = tmp_path / "source.zip"
    with zipfile.ZipFile(path, "w") as output:
        for name, data in entries:
            output.writestr(name, data)
    return path, hashlib.sha256(path.read_bytes()).hexdigest()


@pytest.mark.parametrize("name", ["../escape", "/absolute", "a/../escape", "a\\escape"])
def test_unsafe_members_refused_before_read(tmp_path, name):
    path, digest = archive(tmp_path, [(name, b"unsafe")])
    with pytest.raises(ValueError, match="Unsafe"), SourceArchive(path, digest):
        pass


def test_pinned_bytes_and_member_budget(tmp_path):
    path, digest = archive(tmp_path, [("image", b"12345")])
    with pytest.raises(ValueError, match="checksum"), SourceArchive(path, "0" * 64):
        pass
    with SourceArchive(path, digest) as source:
        assert source.read("image", maximum_bytes=5) == b"12345"
        with pytest.raises(ValueError, match="budget"):
            source.read("image", maximum_bytes=4)


def test_duplicate_members_refused(tmp_path):
    with pytest.warns(UserWarning):
        path, digest = archive(tmp_path, [("image", b"a"), ("image", b"b")])
    with pytest.raises(ValueError, match="Duplicate"), SourceArchive(path, digest):
        pass
