"""Private staging preserves explicit sharing metadata at atomic publication."""

import os
import stat

import pytest
from test_gold_release import materialize, spec
from test_release import sites
from test_release import spec as legacy_spec

from weedz.release import write_release
from weedz.release_storage import staged_release


def mode(path):
    return stat.S_IMODE(path.stat().st_mode)


def test_new_legacy_release_uses_mkdir_permissions(tmp_path):
    previous = os.umask(0o027)
    try:
        expected = tmp_path / "mkdir"
        expected.mkdir()
        output = tmp_path / "release"
        write_release(output, sites("a", "b", "c", "d"), legacy_spec())
    finally:
        os.umask(previous)
    assert mode(output) == mode(expected) == 0o750


@pytest.mark.parametrize("permissions", [0o755, 0o750])
def test_explicit_empty_destination_permissions_survive_publication(tmp_path, permissions):
    output = tmp_path / "release"
    output.mkdir(mode=permissions)
    output.chmod(permissions)
    before = output.stat()
    with staged_release(output) as stage:
        assert mode(stage) == 0o700
        (stage / "proof").write_text("complete")
    assert mode(output) == permissions
    assert output.stat().st_gid == before.st_gid


def test_new_v2_release_stays_private_even_with_permissive_umask(tmp_path):
    source = tmp_path / "source"
    samples = materialize(source)
    previous = os.umask(0o022)
    try:
        output = tmp_path / "release"
        write_release(output, samples, spec(), assets_root=source)
    finally:
        os.umask(previous)
    assert mode(output) == 0o700


def test_new_review_snapshot_staging_remains_private(tmp_path):
    output = tmp_path / "snapshot"
    with staged_release(output) as stage:
        assert mode(stage) == 0o700
    assert mode(output) == 0o700


def test_existing_posix_acl_is_preserved_when_supported(tmp_path):
    import errno
    import struct

    output = tmp_path / "release"
    output.mkdir()
    # Linux POSIX ACL wire format: owner, named user, owning group, mask, other.
    entries = [
        (1, 7, 0xFFFFFFFF),
        (2, 5, os.getuid() + 1),
        (4, 5, 0xFFFFFFFF),
        (16, 5, 0xFFFFFFFF),
        (32, 0, 0xFFFFFFFF),
    ]
    acl = struct.pack("<I", 2) + b"".join(struct.pack("<HHI", *row) for row in entries)
    try:
        os.setxattr(output, "system.posix_acl_access", acl)
    except OSError as error:
        if error.errno in {errno.ENOTSUP, errno.EOPNOTSUPP, errno.EPERM, errno.EINVAL}:
            pytest.skip("Local filesystem does not support this POSIX ACL fixture")
        raise
    expected = os.getxattr(output, "system.posix_acl_access")
    with staged_release(output) as staging:
        assert mode(staging) == 0o700
    assert os.getxattr(output, "system.posix_acl_access") == expected
