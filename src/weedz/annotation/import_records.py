"""Attributable completed annotation revisions, separate from predictions and drafts."""

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any


def digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, allow_nan=False, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def timestamp(value: Any) -> str:
    if not isinstance(value, str):
        raise ValueError("Human revision requires its actual timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            raise ValueError("Timestamp must include its timezone")
    except ValueError as error:
        raise ValueError("Invalid human revision timestamp") from error
    return value


def positive_id(value: Any) -> int:
    if type(value) is not int or value < 1:
        raise ValueError("Expected a positive source account/task/annotation ID")
    return value


@dataclass(frozen=True)
class HumanRecord:
    key: str
    revision: str
    actor: str
    recorded_at: str
    created_at: str
    results: list[dict]
    sha256: str
    author: str
    actor_field: str
    cancelled: bool = False


def _record(row: dict, task_id: int, namespace: str) -> HumanRecord:
    if type(row.get("was_cancelled")) is not bool or positive_id(row.get("task")) != task_id:
        raise ValueError("Human annotation must be completed for the exact task")
    author = _account(row.get("completed_by"), namespace)
    actor_field = "updated_by" if row.get("updated_by") is not None else "completed_by"
    actor = _account(row.get(actor_field), namespace)
    key = f"label-studio:{namespace}:task:{task_id}:annotation:{positive_id(row.get('id'))}"
    recorded = timestamp(row.get("updated_at"))
    created = timestamp(row.get("created_at"))
    if datetime.fromisoformat(recorded.replace("Z", "+00:00")) < datetime.fromisoformat(
        created.replace("Z", "+00:00")
    ):
        raise ValueError("Revision timestamp precedes annotation creation")
    results = row.get("result")
    if not isinstance(results, list) or any(not isinstance(item, dict) for item in results):
        raise ValueError("Completed annotation requires result objects")
    state: dict[str, object] = {
        "actor": actor,
        "created_at": created,
        "updated_at": recorded,
        "result": results,
    }
    if actor_field == "updated_by":
        state.update(annotation_author=author, actor_field=actor_field)
    if row["was_cancelled"]:
        state["was_cancelled"] = True
    return HumanRecord(
        key,
        f"{key}:{recorded}",
        actor,
        recorded,
        created,
        results,
        digest(state),
        author,
        actor_field,
        row["was_cancelled"],
    )


def completed_records(
    task: dict,
    namespace: str,
    *,
    known_cancelled_keys: frozenset[str] = frozenset(),
    source_keys: frozenset[str] = frozenset(),
    source_revision_ids: frozenset[str] = frozenset(),
) -> list[HumanRecord]:
    if not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9._-]{0,99}", namespace):
        raise ValueError("Use a stable source project namespace")
    task_id = positive_id(task.get("id"))
    rows = task.get("annotations", [])
    if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
        raise ValueError("Task annotations must be objects")
    if any(
        f"label-studio:{namespace}:task:{task_id}:annotation:{row.get('id')}" in source_keys
        for row in rows
    ):
        raise ValueError("Human annotation identity collides with immutable source history")
    records = [
        _record(row, task_id, namespace)
        for row in rows
        if _included(row, task_id, namespace, known_cancelled_keys)
    ]
    if any(record.revision in source_revision_ids for record in records):
        raise ValueError("Human revision identity collides with immutable source history")
    if len({record.key for record in records}) != len(records):
        raise ValueError("Duplicate annotation identities in export")
    return records


def _account(value: object, namespace: str) -> str:
    if isinstance(value, dict):
        value = value.get("id")
    return f"label-studio:{namespace}:account:{positive_id(value)}"


def _included(row: dict, task_id: int, namespace: str, known: frozenset[str]) -> bool:
    if row.get("was_cancelled") is not True:
        return True
    return f"label-studio:{namespace}:task:{task_id}:annotation:{row.get('id')}" in known
