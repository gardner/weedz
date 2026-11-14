"""Group photos from one site visit so repeated views are not counted as independent finds.

A group is a review and counting aid: it does not claim the photos show the same plant.
Links need positive evidence, so unknown, obscured or imprecise details never join a group.
Such photos are reported as ungrouped, never as independent visits.
"""

import math
from collections import Counter
from itertools import combinations
from typing import Any

THRESHOLD_M = 250.0
RULE = (
    "same observer and observed date; public coordinates within "
    f"{THRESHOLD_M:g} m after allowing for both positional-accuracy radii; "
    f"photos with accuracy over {THRESHOLD_M:g} m are ungrouped"
)


def _distance_m(a: dict[str, Any], b: dict[str, Any]) -> float:
    lat1, lon1, lat2, lon2 = map(
        math.radians, [a["latitude"], a["longitude"], b["latitude"], b["longitude"]]
    )
    h = (
        math.sin((lat2 - lat1) / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    )
    return 2 * 6_371_000 * math.asin(math.sqrt(h))


def _linkable(photo: dict[str, Any]) -> bool:
    return (
        photo.get("coordinate_status") == "public"
        and photo.get("latitude") is not None
        and photo.get("longitude") is not None
        and bool(photo.get("observed_on"))
        and bool(photo.get("observer"))
        and (photo.get("positional_accuracy_m") or 0) <= THRESHOLD_M
    )


def _same_visit(a: dict[str, Any], b: dict[str, Any]) -> bool:
    if (a["observer"], a["observed_on"]) != (b["observer"], b["observed_on"]):
        return False
    slack = (a.get("positional_accuracy_m") or 0) + (b.get("positional_accuracy_m") or 0)
    return _distance_m(a, b) - slack <= THRESHOLD_M


def encounter_groups(photos: list[dict[str, Any]]) -> dict[str, str]:
    """Map each photo id to its group id: the lowest photo id among linked photos."""
    parent = {photo["id"]: photo["id"] for photo in photos}

    def root(photo_id: str) -> str:
        while parent[photo_id] != photo_id:
            photo_id = parent[photo_id]
        return photo_id

    linkable = [photo for photo in photos if _linkable(photo)]
    for a, b in combinations(linkable, 2):
        if _same_visit(a, b):
            first, second = sorted([root(a["id"]), root(b["id"])])
            parent[second] = first
    return {photo_id: root(photo_id) for photo_id in parent}


def summarize(photos: list[dict[str, Any]], groups: dict[str, str]) -> dict[str, Any]:
    """Count visits among checkable incidental photos; the rest stay explicitly ungrouped."""
    incidental = [photo for photo in photos if photo["cohort"] == "incidental"]
    linkable = [photo["id"] for photo in incidental if _linkable(photo)]
    return {
        "rule": RULE,
        "incidental_photos": len(incidental),
        "independent_site_visits": len({groups[photo_id] for photo_id in linkable}),
        "ungrouped_photos": len(incidental) - len(linkable),
    }


def with_encounters(photos: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Annotate photos with their site-visit group, its size and whether it could be checked."""
    groups = encounter_groups(photos)
    sizes = Counter(groups.values())
    return [
        photo
        | {
            "encounter_group": groups[photo["id"]],
            "encounter_size": sizes[groups[photo["id"]]],
            "encounter_linkable": _linkable(photo),
        }
        for photo in photos
    ]
