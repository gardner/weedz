"""Explicit annotation/image denominators; duplicate pixels never get a primary aggregate."""

from collections import Counter, defaultdict


def aggregate_boxes(cases: list[dict]) -> dict:
    if not 1 <= len(cases) <= 1000:
        raise ValueError("Use a bounded nonempty collection of evaluated images")
    groups: dict[str, list[str]] = defaultdict(list)
    for case in cases:
        groups[case["image_sha256"]].append(case["sample_id"])
    aliases = [identities for identities in groups.values() if len(identities) > 1]
    grid = [(row["budget"], row["iou_threshold"]) for row in cases[0]["measurements"]]
    if not grid or len(set(grid)) != len(grid):
        raise ValueError("Evaluation grid is empty or repeats measurements")
    if any(
        [(row["budget"], row["iou_threshold"]) for row in case["measurements"]] != grid
        for case in cases
    ):
        raise ValueError("Cases have different evaluation protocols")
    aggregate = (
        None
        if aliases
        else [
            _measurement([case["measurements"][index] for case in cases])
            for index in range(len(grid))
        ]
    )
    return {
        "record_count": len(cases),
        "unique_image_count": len(groups),
        "duplicate_image_groups": aliases,
        "execution_status_counts": dict(Counter(case["proposal_status"] for case in cases)),
        "aggregate": aggregate,
        "aggregation_policy": (
            "Blocked: supply a frozen primary selection excluding ambiguous pixel aliases"
            if aliases
            else "Labelled-region micro recall and per-image macro recall; no independence claim"
        ),
    }


def _measurement(rows: list[dict]) -> dict:
    labelled = sum(row["labelled_regions"] for row in rows)
    matched = sum(row["matched_labelled_regions"] for row in rows)
    defined = [
        row["matched_labelled_regions"] / row["labelled_regions"]
        for row in rows
        if row["labelled_regions"]
    ]
    return {
        "budget": rows[0]["budget"],
        "iou_threshold": rows[0]["iou_threshold"],
        "labelled_regions": labelled,
        "matched_labelled_regions": matched,
        "missed_labelled_regions": labelled - matched,
        "actual_proposals": sum(row["actual_proposals"] for row in rows),
        "unmatched_proposals": sum(row["unmatched_proposals"] for row in rows),
        "labelled_region_recall": matched / labelled if labelled else None,
        "images_with_labelled_regions": len(defined),
        "macro_image_labelled_recall": sum(defined) / len(defined) if defined else None,
        "identification": _identification([row["identification"] for row in rows]),
    }


def _identification(rows: list[dict | None]) -> dict | None:
    if all(row is None for row in rows):
        return None
    if any(row is None for row in rows):
        raise ValueError(
            "Missing identification evidence cannot disappear from aggregate denominators"
        )
    records = [row for row in rows if row is not None]
    supported = sum(row["supported_labelled_regions"] for row in records)
    conditional = sum(row["conditional_top1_count"] for row in records)
    correct = sum(row["conditional_top1_correct"] for row in records)
    assessed = sum(row["assessed_prediction_regions"] for row in records)
    eligible_scopes = sum(len(row["exhaustively_assessed_targets"]) for row in records)
    false_alarms = sum(row["assessed_false_alarm_regions"] for row in records)
    negatives = [target for row in records for target in row["verified_negative_targets"]]
    return {
        "supported_labelled_regions": supported,
        "unsupported_labelled_regions": sum(row["unsupported_labelled_regions"] for row in records),
        "conditional_top1_count": conditional,
        "conditional_top1_correct": correct,
        "conditional_top1_accuracy": correct / conditional if conditional else None,
        "unlocalised_supported_labels": sum(row["unlocalised_supported_labels"] for row in records),
        "misidentified_localised_labels": sum(
            row["misidentified_localised_labels"] for row in records
        ),
        "correctly_identified_labelled_recall": correct / supported if supported else None,
        "false_alarm_assessment": {
            "eligible_target_scopes": eligible_scopes,
            "assessed_predictions": assessed,
            "unassessed_predictions": sum(row["unassessed_false_alarm_regions"] for row in records),
            "false_alarm_regions": false_alarms if eligible_scopes else None,
            "assessed_target_precision": (assessed - false_alarms) / assessed if assessed else None,
        },
        "verified_negative_target_count": len(negatives),
        "correct_negative_target_count": sum(target["correct_negative"] for target in negatives),
    }
