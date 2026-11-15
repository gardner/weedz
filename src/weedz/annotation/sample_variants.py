"""Join immutable regional/tiled outputs to the exact canonical image and proposals."""

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from weedz.annotation.auto_labels import frame_prediction, regional_prediction
from weedz.annotation.semantic import shared_regional_version
from weedz.classification.regions import validate_region_scores


@dataclass(frozen=True)
class Variant:
    document: dict[str, Any]
    rows: dict[str, dict[str, Any]]


def read_variant(path: Path | None, field: str, expected: str | None) -> Variant | None:
    if path is None:
        return None
    document = json.loads(path.read_text(encoding="utf-8"))
    if expected is None or document.get(field) != expected:
        raise ValueError(f"Model {field.replace('_sha256', '')} checksum mismatch")
    rows = {row["external_id"]: row for row in document["predictions"]}
    if len(rows) != len(document["predictions"]):
        raise ValueError("Duplicate variant image identities")
    return Variant(document, rows)


def load_variants(
    manifest: Path, proposals: Path | None, regional: Path | None, tiled: Path | None
) -> dict[str, Variant | None]:
    return {
        "regional": read_variant(
            regional,
            "proposals_sha256",
            hashlib.sha256(proposals.read_bytes()).hexdigest() if proposals else None,
        ),
        "tiled": read_variant(
            tiled, "manifest_sha256", hashlib.sha256(manifest.read_bytes()).hexdigest()
        ),
    }


def _row(variant: Variant, key: str, digest: str) -> dict[str, Any]:
    row = variant.rows.get(key)
    if row is None or row["image_sha256"] != digest:
        raise ValueError("Model variant image checksum or identity mismatch")
    return row


def _masked_topk(row: dict[str, Any]) -> list[dict[str, Any]]:
    masked = row.get("views", {}).get("masked")
    if masked is None or ("topk" in row and row["topk"] != masked):
        raise ValueError("Regional primary classification must match the predetermined masked view")
    return masked


def _regional(
    variant: Variant, key: str, digest: str, proposal: dict | None, size: tuple[int, int]
) -> dict[str, Any]:
    if proposal is None:
        raise ValueError("Regional classifications require their exact source proposals")
    row = _row(variant, key, digest)
    proposed = proposal["segmentation"]["regions"]
    regions = {region["id"]: region for region in proposed}
    classified = row["regions"]
    if (
        len(regions) != len(proposed)
        or len({r["id"] for r in classified}) != len(classified)
        or set(regions) != {r["id"] for r in classified}
    ):
        raise ValueError("Regional classifier and proposal identities disagree")
    pairs = [(regions[r["id"]], _masked_topk(r)) for r in classified]
    metadata = variant.document["model"]
    if metadata.get("pipeline_name") == "WeedScan488":
        for region in classified:
            validate_region_scores(region, metadata)
    shared = shared_regional_version(metadata)
    return regional_prediction(
        pairs,
        metadata,
        size,
        alternatives=classified,
        version_name_override=shared["model_version"],
    )


def add_variants(prepared: list, variants: dict[str, Variant | None]) -> None:
    for sample, _encoded, imported, _frame, proposal in prepared:
        key, digest = imported["meta"]["external_id"], sample.media.sha256
        size = (sample.media.width, sample.media.height)
        regional, tiled = variants["regional"], variants["tiled"]
        if regional is not None:
            prediction = _regional(regional, key, digest, proposal, size)
            imported["predictions"] = [prediction, *imported.get("predictions", [])]
            imported["data"]["pipeline_state"] += "; region taxa proposed"
        if tiled is not None:
            row = _row(tiled, key, digest)
            prediction = frame_prediction(
                row["topk"],
                tiled.document["model"],
                display_name="PlantCLEF tiles auto-label",
                scope="aggregated classification windows, not plant boundaries",
                alternatives=row.get("views", []),
            )
            imported.setdefault("predictions", []).append(prediction)
            imported["data"]["pipeline_state"] += "; tiled taxon proposed"
