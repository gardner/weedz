"""Versioned stage artifacts are resumable evidence, never an unvalidated cache hit."""

import pytest

from weedz.segmentation.artifacts import StageArtifacts


def test_completed_artifacts_roundtrip_and_refuse_changed_inputs(tmp_path):
    artifacts = StageArtifacts(tmp_path, "run")
    inputs = {"image_sha256": "original", "checkpoint": "pinned", "version": 1}
    result = {"status": "empty", "regions": []}
    assert artifacts.read("proposals", "photo", inputs) is None
    artifacts.write("proposals", "photo", inputs, result)
    assert artifacts.read("proposals", "photo", inputs) == result
    with pytest.raises(ValueError, match="provenance"):
        artifacts.read("proposals", "photo", inputs | {"image_sha256": "replaced"})


def test_incomplete_failed_stage_is_not_a_successful_cache_hit(tmp_path):
    artifacts = StageArtifacts(tmp_path, "run")
    artifacts.write("proposals", "photo", {"revision": 1}, {"status": "failed", "regions": []})
    failed = artifacts.read("proposals", "photo", {"revision": 1})
    assert failed and failed["status"] == "failed"
    artifacts.write("proposals", "photo", {"revision": 1}, {"status": "ok", "regions": []})
    complete = artifacts.read("proposals", "photo", {"revision": 1})
    assert complete and complete["status"] == "ok"


def test_tampered_stage_output_is_not_trusted(tmp_path):
    artifacts = StageArtifacts(tmp_path, "run")
    artifacts.write("proposals", "photo", {}, {"status": "empty", "regions": []})
    path = next(tmp_path.rglob("*.json"))
    path.write_text(path.read_text().replace('"empty"', '"failed"'))
    with pytest.raises(ValueError, match="checksum"):
        artifacts.read("proposals", "photo", {})


def test_completed_evidence_canonically_wins_a_late_matching_retry(tmp_path):
    artifacts = StageArtifacts(tmp_path, "run")
    original = {"status": "empty", "regions": [], "elapsed_seconds": 1.0}
    artifacts.write("proposals", "photo", {}, original)
    path = next(tmp_path.rglob("*.json"))
    encoded = path.read_bytes()
    actual = artifacts.write("proposals", "photo", {}, {**original, "elapsed_seconds": 2.0})
    assert actual == original
    assert path.read_bytes() == encoded


def test_replacement_syncs_directory_before_reporting_success(tmp_path, monkeypatch):
    import os
    import stat

    original = os.fsync
    synced = []

    def sync(fd):
        synced.append("directory" if stat.S_ISDIR(os.fstat(fd).st_mode) else "file")
        original(fd)

    monkeypatch.setattr(os, "fsync", sync)
    StageArtifacts(tmp_path, "run").write("proposals", "photo", {}, {"status": "empty"})
    assert synced[-2:] == ["file", "directory"]


def test_directory_sync_failure_is_not_acknowledged(tmp_path, monkeypatch):
    artifacts = StageArtifacts(tmp_path, "run")
    artifacts.root.mkdir(parents=True)

    def unavailable(_path):
        raise OSError("Directory sync failed")

    monkeypatch.setattr("weedz.segmentation.artifacts.sync_directory", unavailable)
    with pytest.raises(OSError, match="sync failed"):
        artifacts.write("proposals", "photo", {}, {"status": "empty"})


def test_retry_reestablishes_directory_durability_before_cached_success(tmp_path, monkeypatch):
    from weedz.segmentation import artifacts as module

    artifacts = StageArtifacts(tmp_path, "run")
    artifacts.root.mkdir(parents=True)
    original = module.sync_directory
    calls = []
    failed = False

    def fail_after_rename(path):
        nonlocal failed
        calls.append(path)
        if len(calls) == 5 and not failed:
            failed = True
            raise OSError("Interrupted after replacement")
        original(path)

    monkeypatch.setattr(module, "sync_directory", fail_after_rename)
    with pytest.raises(OSError, match="replacement"):
        artifacts.write("proposals", "photo", {}, {"status": "empty"})
    calls.clear()
    assert artifacts.entry("proposals", "photo")
    assert calls[:4] == [
        artifacts.root,
        artifacts.root.parent,
        artifacts.root.parent.parent,
        tmp_path,
    ]
    calls.clear()
    assert artifacts.write("proposals", "photo", {}, {"status": "empty"}) == {"status": "empty"}
    assert calls[:4] == [
        artifacts.root,
        artifacts.root.parent,
        artifacts.root.parent.parent,
        tmp_path,
    ]


def test_late_failed_proposal_view_cannot_erase_retained_masks(tmp_path):
    artifacts = StageArtifacts(tmp_path, "run")
    retained = {
        "status": "failed",
        "proposal_status": "ok",
        "view_status": "failed",
        "regions": [{"id": "real-proposal"}],
    }
    skipped = {
        "status": "failed",
        "proposal_status": "failed",
        "view_status": "skipped_proposal_failure",
        "regions": [],
    }
    artifacts.write("views", "photo", {}, retained)
    assert artifacts.write("views", "photo", {}, skipped) == retained
