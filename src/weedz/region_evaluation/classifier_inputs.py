"""Pinned top-k regional evidence; raw margins are never converted to probabilities."""

import hashlib
import json
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from weedz.classification.regions import validate_region_scores
from weedz.contract import Sample
from weedz.region_evaluation.proposal_inputs import ProposalBatch, _pinned
from weedz.segmentation.artifacts import digest


@dataclass(frozen=True)
class RegionalClassifications:
    sha256: str
    manifest_sha256: str
    model_version: str
    metadata: dict
    rows: dict[str, dict[str, dict]]
    source_sample_count: int
    excluded_sample_ids: tuple[str, ...]


def load_classifier(
    path: Path,
    sha256: str,
    samples: Sequence[Sample],
    proposals: ProposalBatch,
    *,
    allow_subset: bool = False,
) -> RegionalClassifications:
    encoded = _pinned(path, sha256, 128_000_000)
    document = json.loads(encoded)
    _header(document, proposals)
    predicted = document.get("predictions")
    if not isinstance(predicted, list) or not 1 <= len(predicted) <= 1000:
        raise ValueError("Incomplete classifier source rows")
    if not allow_subset and len(predicted) != len(samples):
        raise ValueError("Classifier sample count differs from evaluation")
    keys = [row.get("source_id") for row in predicted]
    if any(not isinstance(key, str) for key in keys) or len(set(keys)) != len(keys):
        raise ValueError("Duplicate or invalid classifier sample identity")
    expected = {sample.id: sample for sample in samples}
    selected = {}
    for row in predicted:
        if row["source_id"] in expected:
            sample = expected[row["source_id"]]
            selected[sample.id] = _regions(row, sample, proposals, document)
    if len(selected) != len(expected):
        raise ValueError("Missing selected classifier source rows")
    return RegionalClassifications(
        sha256,
        document["manifest_sha256"],
        document["model_version"],
        document["model"],
        selected,
        len(predicted),
        tuple(sorted(set(keys) - expected.keys())),
    )


def _header(document: dict, proposals: ProposalBatch) -> None:
    if document.get("schema") != 1 or not isinstance(document.get("model"), dict):
        raise ValueError("Unsupported regional classifier evidence")
    if document.get("proposals_sha256") != proposals.proposals_sha256:
        raise ValueError("Classifier proposal checksum differs from selected localisation evidence")
    metadata = document["model"]
    kind = metadata.get("proposer_kind")
    name = metadata.get("pipeline_name", "PlantCLEF")
    expected = f"{str(kind).upper()} + {name} masked · {digest(metadata)[:12]}"
    if kind not in {"sam2", "sam3"} or document.get("model_version") != expected:
        raise ValueError("Classifier model version does not bind its declared profile")
    if metadata.get("primary_view") != "masked" or metadata.get("crop_geometry_revision") != 2:
        raise ValueError("Unsupported regional classifier crop policy")
    if any(
        row["segmentation"].get("provenance") != metadata.get("proposer")
        for row in proposals.rows.values()
    ):
        raise ValueError("Classifier proposer profile differs from localisation evidence")
    if "result_sha256" in document:
        body = {key: value for key, value in document.items() if key != "result_sha256"}
        if digest(body) != document["result_sha256"]:
            raise ValueError("Classifier internal checksum mismatch")


def _regions(
    row: dict, sample: Sample, proposals: ProposalBatch, document: dict
) -> dict[str, dict]:
    external = hashlib.sha256(f"{sample.id}:{sample.media.sha256}".encode()).hexdigest()
    if (
        row.get("external_id") != external
        or row.get("image_sha256") != sample.media.sha256
        or row.get("model_version") != document["model_version"]
    ):
        raise ValueError("Classifier source media/model identity differs")
    regions = row.get("regions")
    expected = [record["id"] for record in proposals.rows[sample.id]["segmentation"]["regions"]]
    if not isinstance(regions, list) or [record["id"] for record in regions] != expected:
        raise ValueError("Classifier region identities differ from proposal evidence")
    selected = {}
    for region in regions:
        validate_region_scores(region, document["model"])
        selected[region["id"]] = region["topk"][0]
    return selected
