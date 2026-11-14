"""SQLite review store; idempotent activities never overwrite human decisions."""

import json
import sqlite3
from collections import Counter
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from weedz.discovery.records import Photo, RunSpec


def now() -> str:
    return datetime.now(UTC).isoformat()


def add_missing_column(
    db: sqlite3.Connection, table: str, column: str, definition: str = "TEXT NOT NULL DEFAULT ''"
) -> None:
    if column not in {row["name"] for row in db.execute(f"PRAGMA table_info({table})")}:
        db.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


def reviewer_decisions(events: list[sqlite3.Row]) -> dict[str, dict[str, str]]:
    """Each attributed reviewer's latest standing decision, per photo."""
    decisions: dict[str, dict[str, str]] = {}
    for event in events:
        by_reviewer = decisions.setdefault(event["photo_id"], {})
        if not event["reviewer"]:
            continue
        if event["status"] == "unreviewed":
            by_reviewer.pop(event["reviewer"], None)
        else:
            by_reviewer[event["reviewer"]] = event["status"]
    return decisions


class Store:
    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.database = self.root / "discovery.sqlite3"
        with self.connect() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS runs (
                    id TEXT PRIMARY KEY, created_at TEXT NOT NULL, spec TEXT NOT NULL,
                    status TEXT NOT NULL, detail TEXT NOT NULL DEFAULT '',
                    model TEXT NOT NULL DEFAULT '{}'
                );
                CREATE TABLE IF NOT EXISTS photos (
                    run_id TEXT NOT NULL REFERENCES runs(id), id TEXT NOT NULL,
                    record TEXT NOT NULL, scores TEXT NOT NULL DEFAULT '{}',
                    review_status TEXT NOT NULL DEFAULT 'unreviewed',
                    review_note TEXT NOT NULL DEFAULT '',
                    review_reviewer TEXT NOT NULL DEFAULT '', PRIMARY KEY(run_id, id)
                );
                CREATE TABLE IF NOT EXISTS reviews (
                    id INTEGER PRIMARY KEY, run_id TEXT NOT NULL, photo_id TEXT NOT NULL,
                    status TEXT NOT NULL, note TEXT NOT NULL, created_at TEXT NOT NULL,
                    reviewer TEXT NOT NULL DEFAULT '', effort_seconds REAL,
                    FOREIGN KEY(run_id, photo_id) REFERENCES photos(run_id, id)
                );
            """)
            # Databases created before reviewer attribution keep their history unattributed.
            add_missing_column(db, "photos", "review_reviewer")
            add_missing_column(db, "reviews", "reviewer")
            # Earlier decisions were not timed: NULL means unmeasured, never zero effort.
            add_missing_column(db, "reviews", "effort_seconds", "REAL")

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        db = sqlite3.connect(self.database, timeout=30)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        db.execute("PRAGMA journal_mode=WAL")
        try:
            with db:
                yield db
        finally:
            db.close()

    def create_run(self, run_id: str, spec: RunSpec) -> None:
        with self.connect() as db:
            db.execute(
                "INSERT OR IGNORE INTO runs(id,created_at,spec,status) VALUES(?,?,?,?)",
                (run_id, now(), spec.model_dump_json(), "queued"),
            )

    def status(self, run_id: str, status: str, detail: str = "") -> None:
        with self.connect() as db:
            db.execute("UPDATE runs SET status=?, detail=? WHERE id=?", (status, detail, run_id))

    def model(self, run_id: str, metadata: dict) -> None:
        with self.connect() as db:
            db.execute("UPDATE runs SET model=? WHERE id=?", (json.dumps(metadata), run_id))

    def runs(self) -> list[dict[str, Any]]:
        with self.connect() as db:
            rows = db.execute("SELECT * FROM runs ORDER BY created_at DESC").fetchall()
        return [
            dict(row, spec=json.loads(row["spec"]), model=json.loads(row["model"])) for row in rows
        ]

    def save_photos(self, run_id: str, photos: list[Photo]) -> None:
        with self.connect() as db:
            db.executemany(
                "INSERT INTO photos(run_id,id,record) VALUES(?,?,?) "
                "ON CONFLICT(run_id,id) DO UPDATE SET record=excluded.record",
                [(run_id, photo.id, photo.model_dump_json()) for photo in photos],
            )

    def photos(self, run_id: str) -> list[dict[str, Any]]:
        with self.connect() as db:
            rows = db.execute(
                "SELECT * FROM photos WHERE run_id=? ORDER BY id", (run_id,)
            ).fetchall()
            events = db.execute(
                "SELECT photo_id, reviewer, status FROM reviews WHERE run_id=? ORDER BY id",
                (run_id,),
            ).fetchall()
        decisions = reviewer_decisions(events)
        counts = Counter(event["photo_id"] for event in events)
        return [
            dict(
                json.loads(row["record"]),
                scores=json.loads(row["scores"]),
                review_status=row["review_status"],
                review_note=row["review_note"],
                review_reviewer=row["review_reviewer"],
                reviewer_decisions=decisions.get(row["id"], {}),
                disputed=len(set(decisions.get(row["id"], {}).values())) > 1,
                review_count=counts[row["id"]],
            )
            for row in rows
        ]

    def score(self, run_id: str, photo_id: str, scores: dict) -> None:
        with self.connect() as db:
            db.execute(
                "UPDATE photos SET scores=? WHERE run_id=? AND id=?",
                (json.dumps(scores), run_id, photo_id),
            )

    def review(
        self,
        run_id: str,
        photo_id: str,
        status: str,
        note: str,
        reviewer: str,
        effort_seconds: float | None = None,
    ) -> None:
        if status not in {"unreviewed", "confirmed", "rejected", "uncertain"}:
            raise ValueError("Unknown review status")
        with self.connect() as db:
            cursor = db.execute(
                "UPDATE photos SET review_status=?, review_note=?, review_reviewer=? "
                "WHERE run_id=? AND id=?",
                (status, note, reviewer, run_id, photo_id),
            )
            if cursor.rowcount != 1:
                raise KeyError(photo_id)
            db.execute(
                "INSERT INTO reviews(run_id,photo_id,status,note,created_at,reviewer,"
                "effort_seconds) VALUES(?,?,?,?,?,?,?)",
                (run_id, photo_id, status, note, now(), reviewer, effort_seconds),
            )

    def reviews(self, run_id: str, photo_id: str) -> list[dict]:
        with self.connect() as db:
            return [
                dict(row)
                for row in db.execute(
                    "SELECT * FROM reviews WHERE run_id=? AND photo_id=? ORDER BY id",
                    (run_id, photo_id),
                )
            ]
