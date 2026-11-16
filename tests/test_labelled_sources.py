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


def test_tar_probe_rewinds_same_verified_descriptor(tmp_path):
    import io
    import tarfile

    path = tmp_path / "source.tar.gz"
    with tarfile.open(path, "w:gz") as output:
        member = tarfile.TarInfo("folder/image")
        member.size = 4
        output.addfile(member, io.BytesIO(b"four"))
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    with SourceArchive(path, digest) as source:
        assert source.read("folder/image") == b"four"
        replacement = tmp_path / "other"
        replacement.write_bytes(b"unrelated path bytes")
        replacement.replace(path)
        assert source.read("folder/image") == b"four"
        source.verify()


def test_zip_symlink_refused_without_touching_target(tmp_path):
    path = tmp_path / "source.zip"
    member = zipfile.ZipInfo("link")
    member.create_system = 3
    member.external_attr = 0o120777 << 16
    with zipfile.ZipFile(path, "w") as output:
        output.writestr(member, "/outside/private")
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    with pytest.raises(ValueError, match="symlink"), SourceArchive(path, digest):
        pass


def test_zip_original_nul_name_is_not_silently_normalized(tmp_path):
    path, _ = archive(tmp_path, [("goodXevil", b"payload")])
    path.write_bytes(path.read_bytes().replace(b"goodXevil", b"good\x00evil"))
    sha = hashlib.sha256(path.read_bytes()).hexdigest()
    with pytest.raises(ValueError, match="Unsafe"), SourceArchive(path, sha):
        pass


def test_unicode_path_extra_cannot_alias_another_source_member(tmp_path):
    import struct
    import zlib

    path = tmp_path / "source.zip"
    original = "images/a.jpg"
    target = "images/b.jpg"
    payload = b"\x01" + struct.pack("<I", zlib.crc32(original.encode())) + target.encode()
    renamed = zipfile.ZipInfo(original)
    renamed.extra = struct.pack("<HH", 0x7075, len(payload)) + payload
    with zipfile.ZipFile(path, "w") as output:
        output.writestr(target, b"REAL")
        output.writestr(renamed, b"EVIL")
    sha = hashlib.sha256(path.read_bytes()).hexdigest()
    with pytest.raises(ValueError, match="normalized"), SourceArchive(path, sha):
        pass
