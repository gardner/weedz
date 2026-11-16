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


def _record(row: dict, task_id: int, namespace: str) -> HumanRecord:
    if row.get("was_cancelled") is not False or row.get("task") != task_id:
        raise ValueError("Human annotation must be completed for the exact task")
    author = row.get("completed_by")
    if isinstance(author, dict):
        author = author.get("id")
    author_id = positive_id(author)
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
    actor = f"label-studio:{namespace}:account:{author_id}"
    return HumanRecord(
        key,
        f"{key}:{recorded}",
        actor,
        recorded,
        created,
        results,
        digest({"actor": actor, "created_at": created, "updated_at": recorded, "result": results}),
    )


def completed_records(task: dict, namespace: str) -> list[HumanRecord]:
    if not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9._-]{0,99}", namespace):
        raise ValueError("Use a stable source project namespace")
    task_id = positive_id(task.get("id"))
    rows = task.get("annotations", [])
    if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
        raise ValueError("Task annotations must be objects")
    records = [
        _record(row, task_id, namespace) for row in rows if row.get("was_cancelled") is not True
    ]
    if len({record.key for record in records}) != len(records):
        raise ValueError("Duplicate annotation identities in export")
    return records
