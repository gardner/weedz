"""Species proposals on verified SAM masks; masked pixels are the fixed primary view."""

import fcntl
import hashlib
import io
import json
from pathlib import Path
from typing import Literal

from PIL import Image

from weedz.classification.batch import (
    Classifier,
    _check_topk,
    _encoded_result,
    _identity,
    _snapshot,
    _verified_result,
)
from weedz.contract import Sample
from weedz.discovery import inference
from weedz.discovery.inference import file_sha256, square_view
from weedz.manifest import read_manifest, write_atomic
from weedz.segmentation.artifacts import digest
from weedz.segmentation.regions import ProposalConfig
from weedz.segmentation.sam3_image import Sam3Config, restore_concept_regions
from weedz.segmentation.stages import restored_regions

Proposer = Literal["sam2", "sam3"]


def _inputs(manifest: Path, manifest_sha: str, encoded: bytes, root: Path):
    samples = read_manifest(manifest, manifest_sha)
    if not 1 <= len(samples) <= 1000:
        raise ValueError("Use a nonempty batch of at most 1000 samples")
    rows = [json.loads(line) for line in encoded.splitlines() if line.strip()]
    if len(rows) != len(samples):
        raise ValueError("Incomplete proposal rows")
    for sample, row in zip(samples, rows, strict=True):
        _snapshot(sample, root)
        if row.get("sample_id") != sample.id or row.get("image_sha256") != sample.media.sha256:
            raise ValueError("Proposal asset provenance mismatch")
        stage = row["segmentation"]
        if stage["status"] not in {"ok", "empty"}:
            raise ValueError("Classification requires completed segmentation")
        if bool(stage["regions"]) != (stage["status"] == "ok"):
            raise ValueError("Segmentation status and regions disagree")
    return samples, rows


def _restore(encoded: bytes, expected_sha: str, stage: dict, proposer: Proposer) -> list:
    records = stage["regions"]
    if proposer == "sam2":
        with Image.open(io.BytesIO(encoded)) as image:
            return restored_regions(
                image,
                [{k: v for k, v in r.items() if k != "views"} for r in records],
                ProposalConfig(**stage["provenance"]["proposal_config"]),
            )
    config = Sam3Config(**stage["provenance"]["config"])
    return restore_concept_regions(encoded, records, config, expected_sha256=expected_sha)


def _restored_photo(sample: Sample, source: dict, root: Path, proposer: Proposer) -> tuple:
    stage = source["segmentation"]
    ids = [record["id"] for record in stage["regions"]]
    if len(set(ids)) != len(ids):
        raise ValueError("Duplicate region identities")
    encoded = _snapshot(sample, root)
    expected_sha = sample.media.sha256
    if not expected_sha:
        raise ValueError("Missing regional source checksum")
    return _restore(encoded, expected_sha, stage, proposer), ids


def _cached(
    output: Path,
    header: dict,
    samples: list[Sample],
    proposed: list[dict],
    sha: str | None,
    root: Path,
    proposer: Proposer,
):
    result = _verified_result(output, sha)
    if any(digest({key: result.get(key)}) != digest({key: value}) for key, value in header.items()):
        raise ValueError("Existing regional batch has different provenance")
    rows = result.get("predictions")
    if not isinstance(rows, list) or len(rows) != len(samples):
        raise ValueError("Incomplete regional prediction rows")
    for sample, source, row in zip(samples, proposed, rows, strict=True):
        _restored_photo(sample, source, root, proposer)
        expected = _identity(sample, header["model_version"])
        if any(row.get(key) != value for key, value in expected.items()):
            raise ValueError("Cached regional asset identity mismatch")
        regions = row["regions"]
        if [r["id"] for r in regions] != [r["id"] for r in source["segmentation"]["regions"]]:
            raise ValueError("Cached region identities differ")
        for region in regions:
            validate_region_scores(region, header["model"])
    return result


def validate_region_scores(region: dict, metadata: dict) -> None:
    """Validate all declared views on both normal retries and external adoption."""
    _check_topk(region["topk"])
    if region["topk"] != region["views"].get("masked"):
        raise ValueError("Cached primary classifier view changed")
    if metadata.get("pipeline_name") == "WeedScan488":
        if set(region["views"]) != {"tight", "masked", "context"}:
            raise ValueError("Incomplete WeedScan regional views")
        for topk in region["views"].values():
            _check_topk(topk)


def _predict(samples, rows, root, model, proposer, version):
    result = []
    for sample, row in zip(samples, rows, strict=True):
        regions, ids = _restored_photo(sample, row, root, proposer)
        classified = []
        for start in range(0, len(regions), 32):
            part = regions[start : start + 32]
            names = (
                ("tight", "masked", "context")
                if model.metadata.get("pipeline_name") == "WeedScan488"
                else ("masked",)
            )
            predictions = {}
            for name in names:
                views = [region.views[name] for region in part]
                predictions[name] = model.predict(
                    [square_view(view, (0, 0, *view.size)) for view in views]
                )
                if len(predictions[name]) != len(part):
                    raise ValueError("Regional classifier returned a different image count")
            for index, region_id in enumerate(ids[start : start + 32]):
                alternatives = {name: predictions[name][index] for name in names}
                for topk in alternatives.values():
                    _check_topk(topk)
                classified.append(
                    {"id": region_id, "topk": alternatives["masked"], "views": alternatives}
                )
        result.append({**_identity(sample, version), "regions": classified})
    return result


def regional_metadata(model: Classifier, provenance: dict, proposer: Proposer) -> dict:
    """Share the exact crop policy with workflow preflight without loading a model."""
    metadata = {
        **model.metadata,
        "input_policy": (
            "Actual SAM masked crop, centred neutral square letterbox before timm transform; "
            "source taxonomy not supplied"
        ),
        "proposer": provenance,
        "proposer_kind": proposer,
        "primary_view": "masked",
        "crop_geometry_revision": 2,
        "masked_view_policy": {
            "padding": "centred square",
            "colour": list(inference.LETTERBOX),
            "transform": "recorded timm preprocessing",
        },
    }
    if model.metadata.get("pipeline_name") == "WeedScan488":
        metadata["input_policy"] = (
            "Source-bound SAM tight/masked/context crops; complete neutral square letterbox "
            "before WeedScan bicubic480 preprocessing; no source taxonomy supplied"
        )
        metadata["views"] = ["tight", "masked", "context"]
        metadata["masked_view_policy"]["transform"] = "recorded WeedScan RGB preprocessing"
    return json.loads(json.dumps(metadata, allow_nan=False))


def _check_expected_inputs(
    manifest_sha: str,
    proposals_sha: str,
    expected_manifest: str | None,
    expected_proposals: str | None,
) -> None:
    for name, actual, expected in (
        ("manifest", manifest_sha, expected_manifest),
        ("proposal", proposals_sha, expected_proposals),
    ):
        if expected is not None and actual != expected:
            raise ValueError(f"Regional {name} checksum differs from its pinned input")


def classify_region_batch(
    manifest: Path,
    media_root: Path,
    proposals: Path,
    output: Path,
    model: Classifier,
    proposer: Proposer = "sam2",
    *,
    verified_existing_sha256: str | None = None,
    expected_manifest_sha256: str | None = None,
    expected_proposals_sha256: str | None = None,
) -> dict:
    """Classify closed JSONL proposals, preserving source and mask identities on retries."""
    if proposer not in {"sam2", "sam3"}:
        raise ValueError("Unknown region proposer")
    # Hash and parse exactly the same bounded proposal bytes.
    with proposals.open("rb") as stream:
        encoded = stream.read(128_000_001)
    if len(encoded) > 128_000_000:
        raise ValueError("Proposal batch exceeds the resource cap")
    source_sha, manifest_sha = hashlib.sha256(encoded).hexdigest(), file_sha256(manifest)
    _check_expected_inputs(
        manifest_sha, source_sha, expected_manifest_sha256, expected_proposals_sha256
    )
    samples, rows = _inputs(manifest, manifest_sha, encoded, media_root)
    if file_sha256(proposals) != source_sha or file_sha256(manifest) != manifest_sha:
        raise ValueError("Input provenance changed while reading")
    provenance = rows[0]["segmentation"]["provenance"]
    if any(digest(row["segmentation"]["provenance"]) != digest(provenance) for row in rows):
        raise ValueError("Proposal model provenance differs within the batch")
    metadata = regional_metadata(model, provenance, proposer)
    name = model.metadata.get("pipeline_name", "PlantCLEF")
    version = f"{proposer.upper()} + {name} masked · {digest(metadata)[:12]}"
    header = {
        "schema": 1,
        "model": metadata,
        "model_version": version,
        "manifest_sha256": manifest_sha,
        "proposals_sha256": source_sha,
    }
    if output.exists():
        return _cached(
            output, header, samples, rows, verified_existing_sha256, media_root, proposer
        )
    predicted = _predict(samples, rows, media_root, model, proposer, version)
    body = {**header, "predictions": predicted}
    result = {**body, "result_sha256": digest(body)}
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.with_suffix(output.suffix + ".lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if output.exists():
            return _cached(
                output, header, samples, rows, verified_existing_sha256, media_root, proposer
            )
        write_atomic(output, _encoded_result(result))
    return result
