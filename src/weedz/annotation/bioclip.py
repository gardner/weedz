"""Editable native-margin suggestions; no machine result becomes human truth."""

from weedz.annotation.auto_labels import SAM_POLICY, display_version, taxon_result
from weedz.annotation.label_studio import evidence_result, mask_prediction
from weedz.classification.bioclip import POLICY, candidate, validate_scores
from weedz.classification.bioclip_batches import validate_region


def frame_prediction(scores: dict, metadata: dict) -> dict:
    validate_scores(scores, frame=True)
    return {
        "model_version": display_version("BioCLIP GPU frame+tiles margins", metadata, POLICY),
        "result": [
            taxon_result(candidate(scores)),
            evidence_result(
                {
                    "interpretation": POLICY,
                    "scores": scores,
                    "model": metadata,
                    "scope": (
                        "Existing full-frame and overlapping-tile baseline; "
                        "no source taxonomy supplied"
                    ),
                    "limitations": (
                        "Relative comparison only; Unknown does not establish absence; "
                        "no calibration or held-out accuracy claim"
                    ),
                }
            ),
        ],
    }


def regional_prediction(
    records: list[dict], classified: list[dict], metadata: dict, size: tuple[int, int]
) -> dict:
    if [r["id"] for r in records] != [r["id"] for r in classified]:
        raise ValueError("BioCLIP classifications must match ordered source masks")
    result = []
    for region, record in zip(records, classified, strict=True):
        validate_region(record)
        candidates = [view for view in record["views"].values() if candidate(view) != "Unknown"]
        taxon = (
            candidate(max(candidates, key=lambda view: view["margin"])) if candidates else "Unknown"
        )
        mask, _ = mask_prediction(region, size, label=taxon)
        result.extend([mask, taxon_result(taxon, str(region["id"]))])
    result.append(
        evidence_result(
            {
                "interpretation": SAM_POLICY,
                "alternatives": classified,
                "model": metadata,
                "limitations": (
                    "Tentative relative-margin candidates; partial masks are not complete "
                    "plant boundaries; no verified presence/absence"
                ),
            }
        )
    )
    return {
        "model_version": display_version(
            "SAM + BioCLIP GPU margin verification", metadata, SAM_POLICY
        ),
        "result": result,
    }
