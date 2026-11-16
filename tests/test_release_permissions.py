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


def test_existing_default_acl_is_inherited_by_staged_files(tmp_path):
    import errno
    import struct

    output = tmp_path / "release"
    output.mkdir(mode=0o750)
    entries = [
        (1, 7, 0xFFFFFFFF),
        (2, 6, os.getuid() + 1),
        (4, 4, 0xFFFFFFFF),
        (16, 6, 0xFFFFFFFF),
        (32, 0, 0xFFFFFFFF),
    ]
    acl = struct.pack("<I", 2) + b"".join(struct.pack("<HHI", *row) for row in entries)
    try:
        os.setxattr(output, "system.posix_acl_default", acl)
    except OSError as error:
        if error.errno in {errno.ENOTSUP, errno.EOPNOTSUPP, errno.EPERM, errno.EINVAL}:
            pytest.skip("Local filesystem does not support this POSIX ACL fixture")
        raise
    reference = output / "reference"
    reference.write_bytes(b"reference")
    expected = os.getxattr(reference, "system.posix_acl_access")
    reference.unlink()
    with staged_release(output) as staging:
        assert mode(staging) & 0o777 == 0o700
        payload = staging / "payload"
        payload.write_bytes(b"complete")
        assert os.getxattr(payload, "system.posix_acl_access") == expected
    assert os.getxattr(output, "system.posix_acl_default") == acl
    assert os.getxattr(output / "payload", "system.posix_acl_access") == expected


def test_existing_setgid_is_inherited_by_staged_children(tmp_path):
    output = tmp_path / "release"
    output.mkdir()
    available = [group for group in os.getgroups() if group != output.stat().st_gid]
    if available:
        os.chown(output, -1, available[0])
    output.chmod(0o2750)
    reference = output / "reference"
    reference.mkdir()
    expected_group = reference.stat().st_gid
    expected_setgid = reference.stat().st_mode & stat.S_ISGID
    reference.rmdir()
    assert expected_setgid
    with staged_release(output) as staging:
        assert mode(staging) & 0o777 == 0o700
        child = staging / "child"
        child.mkdir()
        assert child.stat().st_gid == expected_group
        assert child.stat().st_mode & stat.S_ISGID == expected_setgid
    assert mode(output) == 0o2750
