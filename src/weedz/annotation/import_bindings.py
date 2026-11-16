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

    # Old receipts have no explicit table: their retained, pinned exports still
    # record task IDs even for rows without any completed human annotation.
    for exported in history:
        for key, row in exported:
            add(key, row["id"])
    _verify_recorded(prior.task_bindings, bindings)
    for key, row in selected:
        add(key, row["id"])
    return dict(sorted(bindings.items()))


def _verify_recorded(table: object, bindings: dict[str, int]) -> None:
    if table is None:
        return
    if not isinstance(table, dict):
        raise ValueError("Recorded task ID bindings must be an object")
    declared = {key: positive_id(value) for key, value in table.items()}
    if declared != bindings:
        raise ValueError("Recorded task ID bindings differ from the retained exports")
