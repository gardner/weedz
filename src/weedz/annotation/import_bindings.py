"""Closed receipts bind one project task ID to one canonical sample across subsets."""

from collections.abc import Iterable

from weedz.annotation.import_package import Package
from weedz.annotation.import_records import positive_id


def task_bindings(
    prior: Package,
    selected: list[tuple[str, dict]],
    history: Iterable[list[tuple[str, dict]]],
) -> dict[str, int]:
    bindings: dict[str, int] = {}
    reverse: dict[int, str] = {}

    def add(key: str, value: object) -> None:
        identifier = positive_id(value)
        if (
            key not in prior.samples
            or bindings.get(key, identifier) != identifier
            or reverse.get(identifier, key) != key
        ):
            raise ValueError("Canonical sample/task ID binding conflicts with the import chain")
        bindings[key] = identifier
        reverse[identifier] = key

    declared = _recorded(prior.task_bindings)
    for key, value in (declared or {}).items():
        add(key, value)
    for exported in history:
        for key, row in exported:
            _known_historical(declared, key)
            add(key, row["id"])
    for key, row in selected:
        add(key, row["id"])
    return dict(sorted(bindings.items()))


def _recorded(value: object) -> dict[str, int] | None:
    if value is None:
        return None
    if not isinstance(value, dict):
        raise ValueError("Recorded task ID bindings must be an object")
    return {key: positive_id(identifier) for key, identifier in value.items()}


def _known_historical(declared: dict[str, int] | None, key: str) -> None:
    if declared is not None and key not in declared:
        raise ValueError("Owned export task ID binding is missing from the recorded table")
