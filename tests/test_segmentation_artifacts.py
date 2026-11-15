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


def test_completed_evidence_cannot_be_replaced_by_late_retry(tmp_path):
    artifacts = StageArtifacts(tmp_path, "run")
    artifacts.write("proposals", "photo", {}, {"status": "empty", "regions": []})
    with pytest.raises(ValueError, match="completed"):
        artifacts.write("proposals", "photo", {}, {"status": "failed", "regions": []})
