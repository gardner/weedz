"""Explicit scope/review decisions; old presence answers never imply completeness."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Decisions:
    task: str
    review: str
    status: str
    taxa: tuple[str, ...]
    categories: tuple[str, ...]


def _values(results: list[dict], revision: int) -> dict[str, list[str]]:
    allowed = {
        "review_status",
        "completeness_task",
        "completeness_status",
    }
    if type(revision) is not int or revision not in (1, 2):
        raise ValueError("Unsupported human review configuration revision")
    allowed.update(
        {"completeness_scope"}
        if revision == 2
        else {"completeness_taxa", "completeness_categories"}
    )
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
    return values


def decisions(
    results: list[dict], taxa: set[str], categories: set[str], *, revision: int = 1
) -> Decisions:
    values = _values(results, revision)
    task = values.get("completeness_task", [])
    if len(task) != 1 or task[0] not in {"detection", "segmentation"}:
        raise ValueError("Completeness needs an explicit detection/segmentation task")
    review = values.get("review_status", [])
    status = values.get("completeness_status", [])
    if len(review) != 1 or review[0] not in {"unreviewed", "accepted", "rejected", "uncertain"}:
        raise ValueError("An explicit human review decision is required")
    if len(status) != 1 or status[0] not in {"exhaustive", "partial", "unknown"}:
        raise ValueError("An explicit annotation completeness status is required")
    ts, cs = _scopes(values, taxa, categories, revision)
    return Decisions(task[0], review[0], status[0], tuple(sorted(ts)), tuple(sorted(cs)))


def _scopes(
    values: dict[str, list[str]], taxa: set[str], categories: set[str], revision: int
) -> tuple[list[str], list[str]]:
    if revision == 2:
        selected = values.get("completeness_scope", [])
        if not set(selected) <= taxa | categories:
            raise ValueError("Completeness scope differs from the pinned configuration")
        ts, cs = (
            [name for name in selected if name in taxa],
            [name for name in selected if name in categories],
        )
    else:
        ts, cs = values.get("completeness_taxa", []), values.get("completeness_categories", [])
    if not ts and not cs:
        raise ValueError("Completeness requires an explicit named scope")
    if not set(ts) <= taxa or not set(cs) <= categories:
        raise ValueError("Completeness scope differs from the pinned configuration")
    return ts, cs
