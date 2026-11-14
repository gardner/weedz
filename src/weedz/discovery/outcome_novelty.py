"""Reviewers' judged novelty for the outcomes report, kept proportionate (PRD P10).

Each judged plant gets one level: the value its reviewers' standing judgements agree
on, `disputed` when they differ, or `unassessed` when there is none. Only a
`verified_new_locality` with its verification note claims a new locality.
"""

from typing import Any, NamedTuple

from weedz.discovery.judgements import JUDGEMENTS
from weedz.discovery.outcome_terms import Photos, tally

LEVELS = (*(value for value in JUDGEMENTS["novelty"] if value != "unassessed"), "disputed")
RECORD_RELATIVE = {"absent_from_references", "earlier_than_records"}
NEW_LOCALITY = "verified_new_locality"
MEANING = (
    "Judged novelty is each plant's reviewers' standing opinion, by level; reviewers who "
    "differ make it disputed, never a level, and a plant nobody judged stays unassessed. "
    "Only a noted verified_new_locality claims a new locality, with its note as evidence."
)


class Plant(NamedTuple):
    """A confirmed suggestion (no finding id) or a recorded watchlist plant on a photo."""

    photo: dict[str, Any]
    species: str | None
    finding_id: int | None
    judgements: dict[str, Any]


def standing(plant: Plant) -> dict[str, dict[str, Any]]:
    """Each reviewer's standing novelty judgement; a new locality counts only with a note."""
    return {
        reviewer: judgement
        for reviewer, judgement in plant.judgements.get("novelty", {}).items()
        if judgement["value"] != NEW_LOCALITY or judgement.get("note", "").strip()
    }


def level(by_reviewer: dict[str, dict[str, Any]]) -> str:
    values = {judgement["value"] for judgement in by_reviewer.values()}
    if not values:
        return "unassessed"
    return values.pop() if len(values) == 1 else "disputed"


def new_localities(plant: Plant, by_reviewer: dict[str, dict[str, Any]]) -> list[dict]:
    """Each reviewer's verified new locality with its note; a recorded plant is named by
    its finding id, the suggestion by none."""
    where = {"photo_id": plant.photo["id"]}
    if plant.finding_id is not None:
        where["finding_id"] = plant.finding_id
    return [
        where | {"reviewer": reviewer, "note": judgement["note"]}
        for reviewer, judgement in by_reviewer.items()
    ]


def judged_novelty(plants: list[Plant], snapshot: str | None) -> dict[str, Any]:
    """Tallies per judged level, each verified new locality with its note, and plants
    with a record-relative claim made against a snapshot other than `snapshot`."""
    by_level: dict[str, Photos] = {name: [] for name in (*LEVELS, "unassessed")}
    localities: list[dict[str, Any]] = []
    stale: Photos = []
    for plant in plants:
        by_reviewer = standing(plant)
        found = level(by_reviewer)
        by_level[found].append(plant.photo)
        if found == NEW_LOCALITY:
            localities += new_localities(plant, by_reviewer)
        if any(
            judgement["value"] in RECORD_RELATIVE
            and judgement.get("reference_snapshot") != snapshot
            for judgement in by_reviewer.values()
        ):
            stale.append(plant.photo)
    return {
        "judged_novelty": {name: tally(photos) for name, photos in by_level.items()},
        "verified_new_localities": localities,
        "record_relative_judged_against_another_snapshot": tally(stale),
    }


def any_judged(evidence: dict[str, Any]) -> bool:
    return any(
        counts["photos"]
        for name, counts in evidence["judged_novelty"].items()
        if name != "unassessed"
    )
