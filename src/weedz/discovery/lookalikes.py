"""Plants most likely to be mistaken for each watchlist weed, and how screening treats them.

Lookalike photos are a separate, source-labelled cohort: they show whether a native or
other plant passes as a weed, but they are not a reviewed false-positive rate.
"""

import statistics
from collections import defaultdict
from typing import Any

# iNaturalist taxon id -> declared lookalike and the watchlist species it resembles.
LOOKALIKES: dict[int, dict[str, str]] = {
    194530: {"name": "Clematis paniculata", "confusable_with": "Clematis vitalba"},
    366722: {"name": "Clematis forsteri", "confusable_with": "Clematis vitalba"},
    70245: {"name": "Clematis foetida", "confusable_with": "Clematis vitalba"},
    379626: {"name": "Austroderia", "confusable_with": "Cortaderia selloana"},
    48538: {"name": "Cytisus scoparius", "confusable_with": "Ulex europaeus"},
    54699: {"name": "Leptospermum scoparium", "confusable_with": "Ulex europaeus"},
    210165: {"name": "Kunzea ericoides", "confusable_with": "Ulex europaeus"},
}
MEANING = (
    "Source-labelled lookalike photos screened like any other photo. "
    "'top_suggestion' counts photos whose top suggestion (what the review desk shows, "
    "whatever its margin) is the weed they resemble; 'positive_confusable_margin' counts "
    "photos where that weed beat every comparison label, whatever the top suggestion; "
    "the two counts are independent. "
    "This is not a reviewed false-positive rate."
)


def _confusable_margin(photo: dict[str, Any]) -> float | None:
    rows = photo.get("scores", {}).get("species", [])
    return next((row["margin"] for row in rows if row["name"] == photo["lookalike_of"]), None)


def summarize_lookalikes(photos: list[dict[str, Any]]) -> dict[str, Any]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for photo in photos:
        if photo.get("cohort") == "lookalike" and photo.get("scores", {}).get("species"):
            groups[photo["lookalike_taxon"]].append(photo)
    by_taxon = {}
    for taxon, members in sorted(groups.items()):
        confusable = members[0]["lookalike_of"]
        margins = [m for photo in members if (m := _confusable_margin(photo)) is not None]
        by_taxon[taxon] = {
            "confusable_with": confusable,
            "screened": len(members),
            "top_suggestion": sum(
                photo["scores"].get("best_species") == confusable for photo in members
            ),
            "positive_confusable_margin": sum(margin > 0 for margin in margins),
            "median_confusable_margin": round(statistics.median(margins), 6) if margins else None,
        }
    return {"meaning": MEANING, "by_taxon": by_taxon}


def lookalike_photos(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Photos from a lookalike collection's result.json, with their image paths in it."""
    return [
        {
            "id": item["id"],
            "cohort": "lookalike",
            "lookalike_taxon": item["lookalike_taxon"],
            "lookalike_of": item["lookalike_of"],
            "image": f"images/{item['id'].split('-')[-1]}.jpg",
        }
        for item in items
    ]
