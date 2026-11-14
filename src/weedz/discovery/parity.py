"""Does an optimised model still screen like the validated reference? (#52)

A candidate (an exported, quantised, lower-precision or smaller image tower) and the
reference score the same photos over the same windows. Both are read the way a run
reads them (ranking revision 4: frame or any non-featureless tile, best target margin
over every comparison label), and this module reports what would change for a
reviewer: top suggestions, margins, the review queue at fixed budgets, lookalikes
passing as weeds, and reference photos no longer found.

Parity is agreement with the reference, not accuracy: the reference itself is only
validated on small source-labelled samples. The pass/fail limits are fixed in
THRESHOLDS with their reasons; changing one is a new version, never a silent re-tune.
"""

from collections.abc import Mapping, Sequence
from typing import Any

import numpy as np

from weedz.discovery.framing import arm_windows, overlap, ranked
from weedz.discovery.inference import region_boxes, summarize_scores
from weedz.discovery.records import SPECIES

BUDGETS = (5, 10, 20)
MAX_MARGIN_DRIFT = 0.01
THRESHOLDS: dict[str, Any] = {
    "version": 1,
    "limits": {
        "max_margin_drift": MAX_MARGIN_DRIFT,
        "unexplained_top_changes": 0,
        "references_lost": 0,
        "lookalikes_newly_positive": 0,
        "incidental_queue_swaps": 1,
    },
    "why": {
        "max_margin_drift": (
            "Largest change in any photo's margin for any watchlist species. BioCLIP 2's "
            "only incidental candidate in the pilot sits at +0.009 and its weakest reference "
            "at +0.051, so 0.01 can move a photo that is already at the zero line but cannot "
            "push a validated reference to it."
        ),
        "unexplained_top_changes": (
            "Photos whose top suggestion changes although the reference's winning margin "
            "led the candidate's choice by more than twice the drift limit. If every margin "
            "moves by at most the drift limit, only such near-ties can swap."
        ),
        "references_lost": (
            "Reference photos (source-labelled watchlist weeds) that the reference ranks "
            "as their own weed with a positive margin but the candidate does not. Every "
            "pilot reference passes with both pinned models, so losing one is a regression."
        ),
        "lookalikes_newly_positive": (
            "Lookalike photos (native or other plants) that newly beat every comparison "
            "label as the weed they resemble. Rejecting lookalikes is why BioCLIP 2 became "
            "the default (#14), so an optimisation may not give any of that back."
        ),
        "incidental_queue_swaps": (
            "At each budget, photos in the reference's incidental review queue that the "
            "candidate replaces. One swap per budget is tolerated because most incidental "
            "margins are negative and close together; more means a reviewer would see a "
            "materially different queue."
        ),
    },
}


def readout(result: Mapping[str, Any]) -> dict[str, Any]:
    """Best species, its margin and every species' margin, as ranking revision 4 reads them."""
    scores = np.array(result["window_similarities"], dtype=float)
    boxes = region_boxes(result["width"], result["height"])
    if len(boxes) != len(scores):
        raise ValueError(f"{len(scores)} scored windows, but the image has {len(boxes)}")
    eligible = arm_windows("frame_and_tiles", len(boxes), set(result["featureless_windows"]))
    best = summarize_scores(scores, boxes, list(SPECIES), len(SPECIES), eligible)
    margins = {row["name"]: row["margin"] for row in best["species"]}
    return {"species": best["best_species"], "margin": best["margin"], "margins": margins}


def queue_change(first: list[dict[str, Any]], second: list[dict[str, Any]], budget: int) -> dict:
    """What changes at this budget when `second` replaces `first`."""
    before = [item["photo_id"] for item in first[:budget]]
    after = [item["photo_id"] for item in second[:budget]]
    position = {item["photo_id"]: index for index, item in enumerate(second)}
    shared = overlap(first, second, budget)
    return {
        "budget": budget,
        "shared": shared,
        "swaps": len(before) - shared,
        "max_rank_shift": max(
            (abs(position.get(pid, len(second)) - index) for index, pid in enumerate(before)),
            default=0,
        ),
        "entered": [pid for pid in after if pid not in before],
        "left": [pid for pid in before if pid not in after],
    }


def _top_changes(ref: Mapping[str, dict], cand: Mapping[str, dict]) -> list[dict[str, Any]]:
    changed = []
    for pid, before in ref.items():
        after = cand[pid]
        if after["species"] == before["species"]:
            continue
        gap = before["margin"] - before["margins"][after["species"]]
        changed.append(
            {
                "photo_id": pid,
                "reference": before["species"],
                "candidate": after["species"],
                "reference_gap": round(gap, 6),
                "near_tie": gap <= 2 * MAX_MARGIN_DRIFT,
            }
        )
    return changed


def _margins(ref: Mapping[str, dict], cand: Mapping[str, dict]) -> dict[str, Any]:
    drifts = [
        abs(cand[pid]["margins"][name] - margin)
        for pid, before in ref.items()
        for name, margin in before["margins"].items()
    ]
    return {
        "max_abs_drift": round(max(drifts, default=0.0), 6),
        "median_abs_drift": round(float(np.median(drifts)) if drifts else 0.0, 6),
        "zero_crossings": [
            pid
            for pid, before in ref.items()
            if (before["margin"] > 0) != (cand[pid]["margin"] > 0)
        ],
    }


def _window_drift(reference: Mapping[str, Any], candidate: Mapping[str, Any]) -> float:
    drift = 0.0
    for pid, result in reference.items():
        before = np.array(result["window_similarities"], dtype=float)
        after = np.array(candidate[pid]["window_similarities"], dtype=float)
        if before.shape != after.shape:
            raise ValueError(f"{pid}: reference and candidate scored different windows")
        drift = max(drift, float(np.abs(after - before).max(initial=0.0)))
    return round(drift, 6)


def _lookalike_tally(reads: Mapping[str, dict], resembles: Mapping[str, str]) -> dict[str, int]:
    return {
        "top": sum(reads[pid]["species"] == weed for pid, weed in resembles.items()),
        "positive": sum(reads[pid]["margins"][weed] > 0 for pid, weed in resembles.items()),
        "of": len(resembles),
    }


def _lookalikes(ref: Mapping[str, dict], cand: Mapping[str, dict], resembles: dict) -> dict:
    def newly(test: Any) -> list[str]:
        return [
            pid for pid, weed in resembles.items() if test(cand[pid], weed) > test(ref[pid], weed)
        ]

    return {
        "reference": _lookalike_tally(ref, resembles),
        "candidate": _lookalike_tally(cand, resembles),
        "newly_top": newly(lambda read, weed: read["species"] == weed),
        "newly_positive": newly(lambda read, weed: read["margins"][weed] > 0),
    }


def _found(read: Mapping[str, Any], weed: str) -> bool:
    return read["species"] == weed and read["margin"] > 0


def _references(ref: Mapping[str, dict], cand: Mapping[str, dict], weeds: dict) -> dict:
    return {
        "reference_found": sum(_found(ref[pid], weed) for pid, weed in weeds.items()),
        "candidate_found": sum(_found(cand[pid], weed) for pid, weed in weeds.items()),
        "lost": [
            pid
            for pid, weed in weeds.items()
            if _found(ref[pid], weed) and not _found(cand[pid], weed)
        ],
    }


def _queues(ref: Mapping[str, dict], cand: Mapping[str, dict], ids: set[str], budgets) -> list:
    first = ranked({pid: read for pid, read in ref.items() if pid in ids})
    second = ranked({pid: read for pid, read in cand.items() if pid in ids})
    return [queue_change(first, second, budget) for budget in budgets]


def _checks(report: Mapping[str, Any], limits: Mapping[str, float]) -> dict[str, Any]:
    values = {
        "max_margin_drift": report["margins"]["max_abs_drift"],
        "unexplained_top_changes": sum(
            not row["near_tie"] for row in report["top_suggestion"]["changed"]
        ),
        "references_lost": len(report["references"]["lost"]),
        "lookalikes_newly_positive": len(report["lookalikes"]["newly_positive"]),
        "incidental_queue_swaps": max(
            (row["swaps"] for row in report["queues"]["incidental"]), default=0
        ),
    }
    return {
        name: {"value": value, "limit": limits[name], "passed": value <= limits[name]}
        for name, value in values.items()
    }


def compare(
    reference: Mapping[str, Mapping[str, Any]],
    candidate: Mapping[str, Mapping[str, Any]],
    photos: Sequence[Mapping[str, Any]],
    budgets: Sequence[int] = BUDGETS,
) -> dict[str, Any]:
    """Every parity measure and check for a candidate against the reference."""
    if set(reference) != set(candidate) or set(reference) != {p["id"] for p in photos}:
        raise ValueError("Reference and candidate must score the same photos")
    ref = {pid: readout(result) for pid, result in reference.items()}
    cand = {pid: readout(result) for pid, result in candidate.items()}
    by_cohort: dict[str, dict[str, str]] = {"incidental": {}, "reference": {}, "lookalike": {}}
    for item in photos:
        weed = item.get("reference_species") or item.get("lookalike_of") or ""
        by_cohort.setdefault(item["cohort"], {})[item["id"]] = weed
    changed = _top_changes(ref, cand)
    report: dict[str, Any] = {
        "thresholds": THRESHOLDS,
        "photos": len(ref),
        "top_suggestion": {"agree": len(ref) - len(changed), "of": len(ref), "changed": changed},
        "margins": _margins(ref, cand),
        "window_similarity_max_abs_drift": _window_drift(reference, candidate),
        "queues": {
            "incidental": _queues(ref, cand, set(by_cohort["incidental"]), budgets),
            "pooled": _queues(ref, cand, set(ref), budgets),
        },
        "lookalikes": _lookalikes(ref, cand, by_cohort["lookalike"]),
        "references": _references(ref, cand, by_cohort["reference"]),
    }
    report["checks"] = _checks(report, THRESHOLDS["limits"])
    report["passed"] = all(check["passed"] for check in report["checks"].values())
    return report


def encoding_cost(
    artefact_bytes: int,
    peak_rss_bytes: int,
    baseline_rss_bytes: int,
    seconds: Sequence[float],
    windows: Sequence[int],
) -> dict[str, Any]:
    """Size on disk, peak memory and per-photo image-encoding time on this machine."""
    megabytes = 1_000_000
    times = np.array(seconds, dtype=float)
    return {
        "artefact_mb": round(artefact_bytes / megabytes, 1),
        "peak_rss_mb": round(peak_rss_bytes / megabytes, 1),
        "peak_rss_above_baseline_mb": round((peak_rss_bytes - baseline_rss_bytes) / megabytes, 1),
        "photos": len(times),
        "seconds_per_photo": {
            "median": round(float(np.median(times)), 3),
            "p90": round(float(np.percentile(times, 90, method="higher")), 3),
            "mean": round(float(times.mean()), 3),
        },
        "milliseconds_per_window": round(1000 * float(times.sum()) / max(1, sum(windows)), 1),
        "windows_per_photo_median": float(np.median(windows)),
    }
