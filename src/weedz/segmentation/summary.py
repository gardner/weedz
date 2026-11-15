"""Expose actual stage completion without describing fallback as successful segmentation."""

from collections import Counter

from weedz.discovery.records import RunSpec
from weedz.discovery.store import Store


def pipeline_summary(store: Store, run_id: str) -> dict | None:
    run = next(item for item in store.runs() if item["id"] == run_id)
    profile = RunSpec.from_saved(run["spec"]).segmentation
    if profile == "off":
        return None
    states = [photo["scores"].get("segmentation", {}) for photo in store.photos(run_id)]
    proposals = Counter(state.get("proposal_status", "missing") for state in states)
    views = Counter(state.get("view_status", "missing") for state in states)
    missing = sum(
        not state.get("proposal_status") or not state.get("view_status") for state in states
    )
    warnings = []
    if proposals["failed"]:
        warnings.append(
            f"SAM proposal generation failed for {proposals['failed']} photos; "
            "baseline fallback retained"
        )
    if views["failed"]:
        warnings.append(
            f"Region classification failed for {views['failed']} photos; baseline fallback retained"
        )
    if missing:
        warnings.append(f"{missing} photos have not completed every requested stage")
    return {
        "schema": 1,
        "profile": profile,
        "count": len(states),
        "completed": len(states) - proposals["failed"] - views["failed"] - missing,
        "failed": proposals["failed"] + views["failed"],
        "missing": missing,
        "outcome": "partial" if warnings else "completed",
        "warnings": warnings,
        "proposals": dict(proposals),
        "region_scoring": dict(views),
        "baseline_retained": True,
        "ranking_policy": (
            "Full-frame/tile baseline unchanged; proposal views are separate "
            "uncalibrated comparisons"
        ),
    }
