"""Restartable device erasure: commit a write barrier before revocation or deletion.

The marker shares the reports transaction lock, so a previously authenticated worker
cannot store a report after erasure starts. Credentials stay in their separate database.
A crash at any later stage leaves a marker that startup or the original device retries.
"""

import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from weedz.intake.submitters import Submitters

SCHEMA = """
CREATE TABLE IF NOT EXISTS submitter_deletions(
    submitter INTEGER PRIMARY KEY, requested_at TEXT NOT NULL, completed_at TEXT
);
"""


def is_deleting(db: sqlite3.Connection, submitter: int) -> bool:
    return (
        db.execute("SELECT 1 FROM submitter_deletions WHERE submitter=?", (submitter,)).fetchone()
        is not None
    )


@dataclass(frozen=True)
class DeletionReceipt:
    requested_at: str
    completed_at: str | None

    @property
    def status(self) -> str:
        return "deleted" if self.completed_at else "pending"

    def as_dict(self) -> dict[str, str | None]:
        return {
            "status": self.status,
            "requested_at": self.requested_at,
            "completed_at": self.completed_at,
        }


class Deletions:
    def __init__(self, root: Path) -> None:
        # Imported here because ReportStore also uses the schema and barrier above.
        from weedz.intake.store import ReportStore

        self.store = ReportStore(root)
        self.submitters = Submitters(root)

    def started(self, submitter: int) -> bool:
        with self.store._transaction() as db:
            return is_deleting(db, submitter)

    def begin(self, submitter: int) -> None:
        """Persist the barrier before any destructive work; this is the point of no return."""
        with self.store._transaction() as db:
            db.execute(
                "INSERT OR IGNORE INTO submitter_deletions VALUES(?,?,NULL)",
                (submitter, _now()),
            )

    def delete(self, submitter: int) -> DeletionReceipt:
        self.begin(submitter)
        self.submitters.revoke(submitter)
        with self.store._transaction() as db:
            row = db.execute(
                "SELECT * FROM submitter_deletions WHERE submitter=?", (submitter,)
            ).fetchone()
            assert row is not None
            if row["completed_at"]:
                return DeletionReceipt(row["requested_at"], row["completed_at"])
            images = db.execute(
                "SELECT image_file FROM reports WHERE submitter=? AND image_file IS NOT NULL",
                (submitter,),
            )
            for image in images:
                (self.store.images / image["image_file"]).unlink(missing_ok=True)
            self.store._sync_images()
            db.execute(
                "UPDATE reports SET body=NULL,content_sha256=NULL,image_file=NULL,consent=NULL,"
                "withdrawn_at=COALESCE(withdrawn_at,?) WHERE submitter=?",
                (row["requested_at"], submitter),
            )
            db.execute("DELETE FROM usage WHERE submitter=?", (submitter,))
            # Crashed uploads can leave crops without any committed owner row. Sweep
            # them under the same writer lock before claiming that erasure completed.
            self.store._sweep(db)
            completed = _now()
            db.execute(
                "UPDATE submitter_deletions SET completed_at=? WHERE submitter=?",
                (completed, submitter),
            )
        return DeletionReceipt(row["requested_at"], completed)

    def resume(self) -> None:
        """Finish interrupted erasures before serving requests."""
        with self.store._transaction() as db:
            pending = [
                row[0]
                for row in db.execute(
                    "SELECT submitter FROM submitter_deletions WHERE completed_at IS NULL"
                )
            ]
        for submitter in pending:
            self.delete(submitter)


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="microseconds")
