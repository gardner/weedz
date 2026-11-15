"""Completion receipts are immutable, durable and small workflow references."""

import json

import pytest

from weedz.batches.receipts import write_receipt
from weedz.batches.storage import read_artifact


def test_identical_retry_reuses_verified_receipt_without_rewriting(tmp_path):
    document = {"schema": 1, "origin": "external-compute", "count": 100}
    first = write_receipt(tmp_path, "runs/batch/stage.json", document)
    path = tmp_path / first["path"]
    before = path.stat().st_mtime_ns
    assert write_receipt(tmp_path, first["path"], document) == first
    assert path.stat().st_mtime_ns == before
    assert json.loads(read_artifact(tmp_path, first, 4096)) == document


def test_conflicting_completion_is_never_overwritten(tmp_path):
    first = write_receipt(tmp_path, "stage.json", {"count": 1})
    before = (tmp_path / first["path"]).read_bytes()
    with pytest.raises(ValueError, match="conflicting"):
        write_receipt(tmp_path, "stage.json", {"count": 2})
    assert (tmp_path / first["path"]).read_bytes() == before


def test_receipt_directory_is_synced_after_atomic_publication(monkeypatch, tmp_path):
    import os
    import stat

    synced = []
    real = os.fsync

    def sync(fd):
        synced.append(stat.S_ISDIR(os.fstat(fd).st_mode))
        return real(fd)

    monkeypatch.setattr("weedz.batches.receipts.os.fsync", sync)
    write_receipt(tmp_path, "stage.json", {"count": 1})
    assert synced == [False, True]
