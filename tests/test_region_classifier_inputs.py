"""Classifier evidence must name the same source pixels and proposal identities."""

import hashlib
import json
from pathlib import Path

import pytest
from region_helpers import sample

from weedz.region_evaluation.classifier_inputs import load_classifier
from weedz.region_evaluation.proposal_inputs import ProposalBatch


def inputs(root: Path):
    record = sample()
    proposed = ProposalBatch(
        "a" * 64,
        "b" * 64,
        "c" * 64,
        "sam:v1",
        {record.id: {"segmentation": {"regions": [{"id": "region:1"}]}}},
    )
    topk = [{"taxon": "Example species", "score": 0.5, "score_kind": "uncalibrated_share"}]
    row = {
        "source_id": record.id,
        "image_sha256": record.media.sha256,
        "external_id": hashlib.sha256(f"{record.id}:{record.media.sha256}".encode()).hexdigest(),
        "model_version": "classifier:v1",
        "regions": [{"id": "region:1", "topk": topk, "views": {"masked": topk}}],
    }
    document = {
        "schema": 1,
        "manifest_sha256": "d" * 64,
        "proposals_sha256": "c" * 64,
        "model": {"labels_sha256": "e" * 64},
        "model_version": "classifier:v1",
        "predictions": [row],
    }
    path = root / "classifier.json"
    path.write_text(json.dumps(document))
    return record, proposed, path, document


def test_classifier_keeps_its_own_manifest_and_bound_proposal_join(tmp_path: Path) -> None:
    record, proposed, path, _ = inputs(tmp_path)
    result = load_classifier(
        path, hashlib.sha256(path.read_bytes()).hexdigest(), [record], proposed
    )
    assert result.manifest_sha256 == "d" * 64
    assert result.rows[record.id]["region:1"]["taxon"] == "Example species"


@pytest.mark.parametrize("damage", ["pixels", "proposal", "missing", "view"])
def test_wrong_or_incomplete_classifier_evidence_refused(tmp_path: Path, damage: str) -> None:
    record, proposed, path, document = inputs(tmp_path)
    row = document["predictions"][0]
    if damage == "pixels":
        row["image_sha256"] = "0" * 64
    elif damage == "proposal":
        document["proposals_sha256"] = "0" * 64
    elif damage == "missing":
        row["regions"] = []
    else:
        row["regions"][0]["views"]["masked"] = []
    path.write_text(json.dumps(document))
    with pytest.raises(ValueError):
        load_classifier(path, hashlib.sha256(path.read_bytes()).hexdigest(), [record], proposed)


def test_internal_digest_does_not_override_requested_external_sha(tmp_path: Path) -> None:
    from weedz.segmentation.artifacts import digest

    record, proposed, path, document = inputs(tmp_path)
    expected = hashlib.sha256(path.read_bytes()).hexdigest()
    document["extra"] = "unrequested but internally re-digested replacement"
    document["result_sha256"] = digest(document)
    path.write_text(json.dumps(document))
    with pytest.raises(ValueError, match="checksum"):
        load_classifier(path, expected, [record], proposed)
