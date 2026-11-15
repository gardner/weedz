"""Editable all-taxa NZ suggestions, separate from plant-only and human annotations."""

from typing import Any

from weedz.annotation.label_studio import evidence_result

POLICY = "top1 closed-set species including fauna/fungi; uncalibrated; released full-frame416/384"


def frame_runtime(metadata: dict[str, Any]) -> dict[str, Any]:
    if metadata.get("pipeline_name") != "Aotearoa NZ":
        from weedz.annotation.semantic import classifier_runtime

        return classifier_runtime(metadata)
    keys = ("onnxruntime", "numpy", "pillow")
    if any(not isinstance(metadata.get(key), str) or not metadata[key].strip() for key in keys):
        raise ValueError("Incomplete Aotearoa runtime declaration")
    return {
        "status": "recorded",
        "framework": "onnxruntime",
        **{key: metadata[key] for key in keys},
    }


def frame_prediction(topk: list[dict[str, Any]], metadata: dict[str, Any]) -> dict[str, Any]:
    from weedz.annotation.auto_labels import display_version, taxon_result, top_taxon

    runtime = frame_runtime(metadata)
    return {
        "model_version": display_version("Aotearoa NZ frame verification v1", metadata, POLICY),
        "result": [
            taxon_result(top_taxon(topk)),
            evidence_result(
                {
                    "interpretation": POLICY,
                    "scope": "whole image under released416/384 centre crop; no species masks",
                    "classifier_runtime": runtime,
                    "all_taxa_supported": True,
                    "class_count": metadata["class_count"],
                    "model": metadata,
                    "topk": topk,
                    "limitations": metadata.get("limitations", []),
                }
            ),
        ],
    }
