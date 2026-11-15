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
