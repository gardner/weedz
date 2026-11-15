"""Editable machine proposals. Only a human's separate annotation can verify them."""

import hashlib
import json
import math
from typing import Any

from weedz.annotation.label_studio import evidence_result, mask_prediction
from weedz.annotation.semantic import classifier_runtime
from weedz.discovery.records import SPECIES

SAM_POLICY = (
    "max finite positive recognized watchlist margin across tight/masked/context; otherwise Unknown"
)
PLANTCLEF_POLICY = "top1 closed-set plant taxon; no calibrated confidence or non-plant rejection"
PROPOSALS_POLICY = (
    "class-agnostic SAM masks; taxon Unknown because region classification was not requested"
)


def version_stamp(metadata: dict[str, Any], policy: str) -> str:
    return hashlib.sha256(
        json.dumps({"model": metadata, "policy": policy}, sort_keys=True, allow_nan=False).encode()
    ).hexdigest()


def display_version(name: str, metadata: dict[str, Any], policy: str) -> str:
    return f"{name} · {version_stamp(metadata, policy)[:8]}"


def taxon_result(taxon: str, region_id: str | None = None) -> dict[str, Any]:
    return {
        "id": region_id or "image-taxon",
        "from_name": "region_taxon" if region_id else "predicted_taxon",
        "to_name": "image",
        "type": "textarea",
        "value": {"text": [taxon]},
    }


def top_taxon(topk: list[dict[str, Any]]) -> str:
    if not topk:
        return "Unknown"
    first = topk[0]
    score = first.get("score")
    name = first.get("taxon")
    if (
        not isinstance(score, (int, float))
        or isinstance(score, bool)
        or not math.isfinite(score)
        or not isinstance(name, str)
        or not name.strip()
    ):
        return "Unknown"
    return name


def brush_class(taxon: str) -> str:
    if taxon == "Unknown":
        return "Unknown"
    return next(
        (name for name in SPECIES if taxon == name or taxon.startswith(f"{name} ")), "Other plant"
    )


def _runtime_evidence(metadata: dict[str, Any]) -> dict[str, Any]:
    if metadata.get("pipeline_name") == "WeedScan488":
        from weedz.annotation.weedscan import runtime as weedscan_runtime

        return {"classifier_runtime": weedscan_runtime(metadata), "model": metadata}
    runtime = classifier_runtime(metadata)
    # Historical version IDs must retain their already-published result shape.
    return {"classifier_runtime": runtime} if runtime["status"] == "recorded" else {}


def frame_prediction(
    topk: list[dict[str, Any]],
    metadata: dict[str, Any],
    *,
    display_name: str = "PlantCLEF frame auto-label",
    scope: str = "whole frame, not mask regions",
    alternatives: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    if metadata.get("pipeline_name") == "WeedScan488":
        if scope != "whole frame, not mask regions" or alternatives is not None:
            raise ValueError("WeedScan supports separate frame and SAM-region predictions")
        from weedz.annotation.weedscan import frame_prediction as weedscan_frame

        return weedscan_frame(topk, metadata)
    if metadata.get("pipeline_name") == "Aotearoa NZ":
        if scope != "whole frame, not mask regions" or alternatives is not None:
            raise ValueError("Aotearoa supports only released frame predictions")
        from weedz.annotation.aotearoa import frame_prediction as nz_frame

        return nz_frame(topk, metadata)
    if metadata.get("pipeline_name") not in {None, "PlantCLEF"}:
        raise ValueError("Unknown frame classifier kind")
    policy = (
        PLANTCLEF_POLICY
        if scope == "whole frame, not mask regions"
        else f"{PLANTCLEF_POLICY}; {scope}"
    )
    return {
        "model_version": display_version(display_name, metadata, policy),
        "result": [
            taxon_result(top_taxon(topk)),
            evidence_result(
                {
                    "interpretation": PLANTCLEF_POLICY,
                    "scope": scope,
                    **_runtime_evidence(metadata),
                    "topk": topk,
                    "limitations": metadata.get("limitations", []),
                    **({"alternatives": alternatives} if alternatives is not None else {}),
                }
            ),
        ],
    }


def proposals_prediction(
    regions: list[dict[str, Any]], metadata: dict[str, Any], size: tuple[int, int]
) -> dict[str, Any]:
    results = []
    for region in regions:
        mask, _ = mask_prediction(region, size, label="Unknown")
        results.extend([mask, taxon_result("Unknown", str(region["id"]))])
    if metadata.get("profile") == "sam3-image-concept-v1":
        name = "SAM3 concept region proposals"
        policy = "Prompt-conditioned SAM3 regions; uncalibrated concept scores, not species labels"
        evidence = {
            "interpretation": policy,
            "concept_regions": [
                {
                    key: region.get(key)
                    for key in ("id", "prompt", "concept_score", "concept_score_kind")
                }
                for region in regions
            ],
        }
    elif metadata.get("profile") in {None, "sam2.1-tiny-v1"}:
        name, policy = "SAM2.1 mask proposals", PROPOSALS_POLICY
        evidence = {"interpretation": policy}
    else:
        raise ValueError("Unknown proposal model profile")
    results.append(evidence_result(evidence))
    return {
        "model_version": display_version(name, metadata, policy),
        "result": results,
    }


def sam_prediction(
    regions: list[dict[str, Any]], metadata: dict[str, Any], size: tuple[int, int]
) -> dict[str, Any]:
    results = []
    for region in regions:
        candidates = [
            view
            for name in ("tight", "masked", "context")
            if (view := region.get("views", {}).get(name))
            and view.get("best_species") in SPECIES
            and type(view.get("margin")) in (float, int)
            and math.isfinite(view["margin"])
            and view["margin"] > 0
        ]
        taxon = (
            max(candidates, key=lambda row: row["margin"])["best_species"]
            if candidates
            else "Unknown"
        )
        mask, _ = mask_prediction(region, size, label=taxon)
        results.extend([mask, taxon_result(taxon, str(region["id"]))])
    results.append(
        evidence_result(
            {
                "interpretation": "Tentative machine labels, not verified identifications",
                "policy": SAM_POLICY,
                "alternatives": [{"id": r["id"], "views": r.get("views", {})} for r in regions],
            }
        )
    )
    return {
        "model_version": display_version("SAM2.1 + BioCLIP2 auto-label", metadata, SAM_POLICY),
        "result": results,
    }


def regional_prediction(
    regions: list[tuple[dict[str, Any], list[dict[str, Any]]]],
    metadata: dict[str, Any],
    size: tuple[int, int],
    alternatives: list[dict[str, Any]] | None = None,
    version_name_override: str | None = None,
) -> dict[str, Any]:
    policy = PLANTCLEF_POLICY
    if metadata.get("pipeline_name") == "WeedScan488":
        from weedz.annotation.weedscan import POLICY

        policy = POLICY
    results = []
    for region, topk in regions:
        taxon = top_taxon(topk)
        mask, _ = mask_prediction(region, size, label=brush_class(taxon))
        results.extend([mask, taxon_result(taxon, str(region["id"]))])
    results.append(
        evidence_result(
            {
                "interpretation": policy,
                "primary_view": "masked (fixed before inspection)",
                **_runtime_evidence(metadata),
                "alternatives": alternatives
                if alternatives is not None
                else [{"id": region["id"], "topk": topk} for region, topk in regions],
                "limitations": metadata.get("limitations", []),
            }
        )
    )
    name = display_version("SAM + PlantCLEF masked", metadata, PLANTCLEF_POLICY)
    if metadata.get("pipeline_name") == "WeedScan488":
        from weedz.annotation.semantic import shared_regional_version

        name = shared_regional_version(metadata)["model_version"]
    if version_name_override is not None:
        from weedz.annotation.semantic import shared_regional_version

        validated = shared_regional_version(metadata)["model_version"]
        if version_name_override != validated:
            raise ValueError("Version override disagrees with semantic pipeline configuration")
        name = validated
    return {
        "model_version": name,
        "result": results,
    }
