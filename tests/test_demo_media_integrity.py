"""Valid media replacements cannot inherit a previous producer's success receipt."""

import hashlib
import importlib
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parents[1] / "tools/demo-video"))
integrity = importlib.import_module("demo_integrity")


@pytest.mark.parametrize("hashes", [None, {}, {"capture.webm": "0" * 64}])
def test_missing_or_changed_media_receipt_is_refused(tmp_path, hashes):
    (tmp_path / "capture.webm").write_bytes(b"replacement video")
    with pytest.raises(ValueError, match="checksum"):
        integrity.checked_files(tmp_path, ("capture.webm",), hashes)


def test_checked_snapshot_is_the_original_even_after_source_replacement(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    media = source / "capture.webm"
    original = b"producer completed bytes"
    media.write_bytes(original)
    target = tmp_path / "private"
    target.mkdir()
    integrity.checked_files(
        source, (media.name,), {media.name: hashlib.sha256(original).hexdigest()}, target
    )
    media.write_bytes(b"replacement after preflight")
    assert (target / media.name).read_bytes() == original
