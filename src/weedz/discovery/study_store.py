"""Studies kept beside runs in the review store: versions appended, never edited.

Each edit is a whole new version of the definition with its author, time and note; the
latest version is the study. A run links to one study at a time; links are appended too,
so the latest stands and the history shows who changed it.
"""

import json
import uuid
from datetime import UTC, datetime
from typing import Any

from weedz.discovery.records import RunSpec
from weedz.discovery.store import Store
from weedz.discovery.study import StudyDefinition, StudyEdit, differences, open_decisions

# The insert itself checks the edit replaces the latest version, so of two people editing
# the same version at once only the first is saved.
INSERT_NEXT = """
INSERT INTO study_versions(study_id,version,definition,author,change_note,created_at)
SELECT ?,?,?,?,?,? WHERE COALESCE(
    (SELECT MAX(version) FROM study_versions WHERE study_id=?), 0
) = ?
"""
LATEST_LINKS = """
SELECT l.* FROM run_studies l WHERE l.id = (
    SELECT MAX(id) FROM run_studies WHERE run_id = l.run_id
)
"""


class AlreadyLinked(Exception):
    """The run already has a study; a new one would replace it unseen."""


class StaleVersion(Exception):
    """The edit was based on a version that is no longer the latest."""


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _version(row: Any) -> dict[str, Any]:
    return dict(row) | {"id": row["study_id"], "definition": json.loads(row["definition"])}


def versions(store: Store, study_id: str) -> list[dict[str, Any]]:
    """Every version of the study, oldest first; empty if there is no such study."""
    with store.connect() as db:
        rows = db.execute(
            "SELECT * FROM study_versions WHERE study_id=? ORDER BY version", (study_id,)
        ).fetchall()
    return [_version(row) for row in rows]


def save_version(store: Store, study_id: str | None, edit: StudyEdit) -> dict[str, Any]:
    """Append the next version of a study (a new study when `study_id` is None)."""
    study_id = study_id or f"study-{uuid.uuid4().hex[:12]}"
    version = edit.base_version + 1
    with store.connect() as db:
        cursor = db.execute(
            INSERT_NEXT,
            (
                study_id,
                version,
                edit.definition.model_dump_json(),
                edit.author,
                edit.change_note,
                _now(),
                study_id,
                edit.base_version,
            ),
        )
    if cursor.rowcount != 1:
        latest = len(versions(store, study_id))
        raise StaleVersion(
            f"This study is at version {latest}, not {edit.base_version}; reload and edit again"
        )
    return {"id": study_id, "version": version}


# Links only if the run has never had a study, in the same write that records it.
LINK_FIRST = """
INSERT INTO run_studies(run_id,study_id,linked_by,created_at)
SELECT ?,?,?,? WHERE NOT EXISTS (SELECT 1 FROM run_studies WHERE run_id=?)
"""


def create_linked(store: Store, run_id: str, edit: StudyEdit) -> dict[str, Any]:
    """Record a new study and link it to a run that has none, in one transaction, so of
    two people creating a study for the same run at once only the first succeeds."""
    study_id = f"study-{uuid.uuid4().hex[:12]}"
    created = _now()
    with store.connect() as db:
        linked = db.execute(LINK_FIRST, (run_id, study_id, edit.author, created, run_id))
        if linked.rowcount == 1:
            db.execute(
                INSERT_NEXT,
                (
                    study_id,
                    1,
                    edit.definition.model_dump_json(),
                    edit.author,
                    edit.change_note,
                    created,
                    study_id,
                    0,
                ),
            )
            return {"id": study_id, "version": 1}
    existing = run_study(store, run_id)
    raise AlreadyLinked(
        f"This run already has study {existing['id'] if existing else ''}; reload and edit it"
    )


def _links(store: Store) -> list[dict[str, Any]]:
    with store.connect() as db:
        return [dict(row) for row in db.execute(LATEST_LINKS + " ORDER BY l.run_id")]


def studies(store: Store) -> list[dict[str, Any]]:
    """Each study's latest version with the runs now linked to it, newest first."""
    with store.connect() as db:
        rows = db.execute(
            "SELECT * FROM study_versions v WHERE version = "
            "(SELECT MAX(version) FROM study_versions WHERE study_id = v.study_id) "
            "ORDER BY created_at DESC"
        ).fetchall()
    links = _links(store)
    return [
        _version(row)
        | {"runs": [link["run_id"] for link in links if link["study_id"] == row["study_id"]]}
        for row in rows
    ]


def link_study(store: Store, run_id: str, study_id: str, linked_by: str) -> None:
    """Link a run to a study; the latest link stands. Raises KeyError for an unknown study."""
    if not versions(store, study_id):
        raise KeyError(study_id)
    with store.connect() as db:
        db.execute(
            "INSERT INTO run_studies(run_id,study_id,linked_by,created_at) VALUES(?,?,?,?)",
            (run_id, study_id, linked_by, _now()),
        )


def run_study(store: Store, run_id: str) -> dict[str, Any] | None:
    """The study now linked to the run, at its latest version, with its open decisions and
    its differences from the screening code and the run; None if no study is linked."""
    link = next((item for item in _links(store) if item["run_id"] == run_id), None)
    if link is None:
        return None
    current = versions(store, link["study_id"])[-1]
    definition = StudyDefinition.stored(current["definition"])
    run = next((item for item in store.runs() if item["id"] == run_id), None)
    # A run with no saved spec (the device-report run) made no bounded query.
    spec = RunSpec.from_saved(run["spec"]) if run and run["spec"] else None
    return current | {
        "linked_by": link["linked_by"],
        "linked_at": link["created_at"],
        "open_decisions": open_decisions(definition),
        "differences": differences(definition, spec),
    }
