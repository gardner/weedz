"""Whole-frame versus tile screening, read from the same window embeddings (#12).

A revision 4 screening result keeps every window's similarities, so each arm is a
different readout of one model pass: only the letterboxed whole frame, only the
non-featureless tiles, or either (what runs use). Each arm ranks photos by margin into
a queue, and a reviewer budget K is measured against labels it is given. Label tiers
are never pooled. An unlabelled photo is unlabelled, never a false alarm, and a tier
without labels is "not measurable" (None), never zero. A tile is a search window from
the same model, not a plant-region proposal followed by a specialist identifier.
"""

from collections.abc import Collection, Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Literal

import numpy as np

from weedz.discovery.inference import region_boxes, summarize_scores
from weedz.discovery.records import SPECIES

Arm = Literal["whole_frame", "tiles", "frame_and_tiles"]
ARMS: dict[Arm, str] = {
    "whole_frame": "Only the letterboxed whole frame may rank a species",
    "tiles": "Only square tiles may rank a species; featureless tiles cannot",
    "frame_and_tiles": "The whole frame or any non-featureless tile (ranking revision 4)",
}
MEANING = (
    "Three readouts of the same window embeddings, each ranking photos by best target "
    "margin. At each budget K a reviewer sees the top K photos. 'found' counts labelled-"
    "present (photo, species) pairs reached with that species as the suggestion; "
    "'known_false_alarms' counts suggestions on labelled-absent pairs; precision is over "
    "labelled items only, so unlabelled photos are counted apart, not as false alarms. "
    "None means not measurable (no labels), not zero. Independent labels are reference-"
    "collection examples eligible for evaluation and agreeing blind audits, both only on "
    "the rank-independent blind audit sample, measured on "
    "the incidental review queue and counted only on incidental photos; a species "
    "labelled both present and absent is left out as unresolved. Source subject labels "
    "are reference photos whose subject is the weed, measured on a pooled queue with "
    "lookalike photos; they describe the subject, not background plants, and a "
    "lookalike is not a verified absence."
)


@dataclass(frozen=True)
class Label:
    photo_id: str
    taxon: str
    present: bool


def arm_windows(arm: Arm, window_count: int, featureless: Collection[int]) -> list[bool]:
    """Which windows may rank a species under this arm; window 0 is the whole frame."""
    if arm not in ARMS:
        raise KeyError(arm)
    frame = arm != "tiles"
    tiles = arm != "whole_frame"
    return [frame] + [tiles and index not in featureless for index in range(1, window_count)]


def suggest(result: Mapping[str, Any], arm: Arm) -> dict[str, Any] | None:
    """The arm's best species, margin and window, or None when no window may rank."""
    scores = np.array(result["window_similarities"], dtype=float)
    boxes = region_boxes(result["width"], result["height"])
    if len(boxes) != len(scores):
        raise ValueError(f"{len(scores)} scored windows, but the image has {len(boxes)}")
    eligible = arm_windows(arm, len(boxes), set(result.get("featureless_windows", [])))
    if not any(eligible):
        return None
    best = summarize_scores(scores, boxes, list(SPECIES), len(SPECIES), eligible)
    return {"species": best["best_species"], "margin": best["margin"], "box": best["box"]}


def ranked(suggestions: Mapping[str, Mapping[str, Any] | None]) -> list[dict[str, Any]]:
    """Photos by margin, highest first (ties by id); unranked photos are left out."""
    queue = [
        {"photo_id": photo_id, "species": found["species"], "margin": found["margin"]}
        for photo_id, found in suggestions.items()
        if found is not None
    ]
    return sorted(queue, key=lambda item: (-item["margin"], item["photo_id"]))


def _ratio(part: int, whole: int) -> float | None:
    return part / whole if whole else None


def at_budget(queue: list[dict[str, Any]], labels: Iterable[Label], budget: int) -> dict:
    """What a reviewer who reviews the top `budget` photos finds, against `labels`."""
    present = {(label.photo_id, label.taxon) for label in labels if label.present}
    absent = {(label.photo_id, label.taxon) for label in labels if not label.present}
    labelled = {pair[0] for pair in present | absent}
    top = queue[:budget]
    found = sum((item["photo_id"], item["species"]) in present for item in top)
    alarms = sum((item["photo_id"], item["species"]) in absent for item in top)
    return {
        "budget": budget,
        "reviewed": len(top),
        "labelled_present": len(present),
        "found": found,
        "recall": _ratio(found, len(present)),
        "known_false_alarms": alarms,
        "precision": _ratio(found, found + alarms),
        "unlabelled": sum(item["photo_id"] not in labelled for item in top),
    }


def lookalikes_reached(
    queue: list[dict[str, Any]], resembles: Mapping[str, str], budget: int
) -> int:
    """Lookalike photos in the top `budget` suggested as the weed they resemble."""
    return sum(resembles.get(item["photo_id"]) == item["species"] for item in queue[:budget])


def overlap(first: list[dict[str, Any]], second: list[dict[str, Any]], budget: int) -> int:
    """Photos two queues both put in front of a reviewer at this budget."""
    ids = {item["photo_id"] for item in first[:budget]}
    return sum(item["photo_id"] in ids for item in second[:budget])


def _audit_labels(photo_id: str, findings: Iterable[str]) -> list[Label]:
    """Agreeing blind findings only: a species is present; "none" is no target visible."""
    answers = set(findings)
    if len(answers) != 1:
        return []
    answer = answers.pop()
    if answer in SPECIES:
        return [Label(photo_id, answer, True)]
    if answer == "none":
        return [Label(photo_id, species, False) for species in SPECIES]
    return []


def independent_labels(
    examples: Iterable[Mapping[str, Any]],
    audits: Mapping[str, Mapping[str, str]],
    sample: Collection[str],
) -> list[Label]:
    """Evaluation-eligible watchlist examples and agreeing blind audits, on the sample only.

    The audit sample is chosen from photo ids, independently of rank. Ranked review meets
    photos in margin order, so its findings elsewhere would favour the arm that ordered
    the queue. Each (photo, species) is labelled once; one labelled both present and
    absent (say, an accepted finding and a blind "none") is unresolved and left out.
    """
    labels = [
        Label(photo_id, example["taxon"], example["label"] == "present")
        for example in examples
        # A pilot sample id is "<source>:<photo id>".
        if (photo_id := example["sample_id"].split(":", 1)[-1]) in sample
        and example["uses"]["evaluation"]["eligible"]
        and example["taxon"] in SPECIES
        and example["label"] in {"present", "absent"}
    ]
    for photo_id in sorted(set(audits) & set(sample)):
        labels += _audit_labels(photo_id, audits[photo_id].values())
    return _consistent(labels)


def _consistent(labels: list[Label]) -> list[Label]:
    """Labels once each, in first-seen order, without pairs that contradict themselves."""
    unique = list(dict.fromkeys(labels))
    present = {(label.photo_id, label.taxon) for label in unique if label.present}
    absent = {(label.photo_id, label.taxon) for label in unique if not label.present}
    return [label for label in unique if (label.photo_id, label.taxon) not in present & absent]


def source_labels(photos: Iterable[Mapping[str, Any]]) -> list[Label]:
    """Reference photos are labelled present for their weed by the source; nothing else is."""
    return [
        Label(photo["id"], photo["reference_species"], True)
        for photo in photos
        if photo["cohort"] == "reference" and photo.get("reference_species")
    ]


def _queue_report(
    queue: list[dict[str, Any]],
    labels: list[Label],
    budgets: list[int],
    resembles: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    rows = []
    for budget in budgets:
        row = at_budget(queue, labels, budget)
        if resembles is not None:
            row["lookalikes_reached"] = lookalikes_reached(queue, resembles, budget)
        rows.append(row)
    return {"queued": len(queue), "budgets": rows}


def _overlaps(queues: Mapping[str, list[dict[str, Any]]], budgets: list[int]) -> dict:
    arms = list(queues)
    return {
        f"{first}|{second}": [overlap(queues[first], queues[second], k) for k in budgets]
        for index, first in enumerate(arms)
        for second in arms[index + 1 :]
    }


def compare(
    results: Mapping[str, Mapping[str, Any]],
    photos: Sequence[Mapping[str, Any]],
    independent: list[Label],
    budgets: list[int],
) -> dict[str, Any]:
    """Every arm's queues and budget measures, per-photo suggestions and label counts."""
    picks = {pid: {arm: suggest(result, arm) for arm in ARMS} for pid, result in results.items()}
    incidental = {photo["id"] for photo in photos if photo["cohort"] == "incidental"}
    resembles = {
        photo["id"]: photo["lookalike_of"] for photo in photos if photo["cohort"] == "lookalike"
    }
    subjects = source_labels(photos)
    # The incidental queue can only reach incidental photos; other labels would deflate
    # recall and make an unmeasured tier look measured.
    independent = [label for label in independent if label.photo_id in incidental]
    queues = {arm: ranked({pid: found[arm] for pid, found in picks.items()}) for arm in ARMS}
    review = {
        arm: [item for item in queue if item["photo_id"] in incidental]
        for arm, queue in queues.items()
    }
    arms = {
        arm: {
            "meaning": ARMS[arm],
            "windows_per_photo": _windows(results.values(), arm),
            "incidental": _queue_report(review[arm], independent, budgets),
            "pooled": _queue_report(queues[arm], subjects, budgets, resembles),
        }
        for arm in ARMS
    }
    return {
        "meaning": MEANING,
        "budgets": budgets,
        "labels": {
            "independent": len(independent),
            "source_subject": len(subjects),
            "lookalike_photos": len(resembles),
        },
        "arms": arms,
        "overlap": {"incidental": _overlaps(review, budgets), "pooled": _overlaps(queues, budgets)},
        "photos": picks,
    }


def _windows(results: Iterable[Mapping[str, Any]], arm: Arm) -> float:
    """Median windows an arm needs encoded per photo: a compute-cost proxy."""
    counts = [
        1 if arm == "whole_frame" else len(region_boxes(r["width"], r["height"])) - (arm == "tiles")
        for r in results
    ]
    return float(np.median(counts)) if counts else 0.0
