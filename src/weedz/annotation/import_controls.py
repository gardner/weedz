"""Explicit scope/review decisions; old presence answers never imply completeness."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Decisions:
    review: str
    status: str
    taxa: tuple[str, ...]
    categories: tuple[str, ...]


def decisions(results: list[dict], taxa: set[str], categories: set[str]) -> Decisions:
    allowed = {
        "review_status",
        "completeness_status",
        "completeness_taxa",
        "completeness_categories",
    }
    values: dict[str, list[str]] = {}
    for row in results:
        if row.get("type") != "choices":
            continue
        name = row.get("from_name")
        chosen = row.get("value", {}).get("choices")
        if (
            name not in allowed
            or name in values
            or row.get("to_name") != "image"
            or not isinstance(chosen, list)
            or any(not isinstance(v, str) for v in chosen)
            or len(set(chosen)) != len(chosen)
        ):
            raise ValueError("Invalid, unknown or duplicate human review control")
        values[name] = chosen
    review = values.get("review_status", [])
    status = values.get("completeness_status", [])
    if len(review) != 1 or review[0] not in {"unreviewed", "accepted", "rejected", "uncertain"}:
        raise ValueError("An explicit human review decision is required")
    if len(status) != 1 or status[0] not in {"exhaustive", "partial", "unknown"}:
        raise ValueError("An explicit annotation completeness status is required")
    ts, cs = values.get("completeness_taxa", []), values.get("completeness_categories", [])
    if not ts and not cs:
        raise ValueError("Completeness requires an explicit named scope")
    if not set(ts) <= taxa or not set(cs) <= categories:
        raise ValueError("Completeness scope differs from the pinned configuration")
    return Decisions(review[0], status[0], tuple(sorted(ts)), tuple(sorted(cs)))
