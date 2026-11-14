"""SQLite review store; idempotent activities never overwrite human decisions."""

import json
import sqlite3
from collections import Counter
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from weedz.discovery.records import Finding, Photo, RunSpec


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


# An audit is blind only if it is the auditor's first answer for the photo (after it the
# photo is released into their ranked queue) and no one reviewed the photo before it
# without having audited it first. The app lets a sampled photo be reviewed only after the
# reviewer's own audit, so any other earlier review, such as one made before the sample
# existed, means the suggestion may have been seen.
AUDITS_BY_BLINDNESS = """
SELECT a.photo_id, a.reviewer, a.finding FROM audits a
WHERE a.run_id = ? AND (
    NOT EXISTS (
        SELECT 1 FROM audits earlier WHERE earlier.run_id = a.run_id
        AND earlier.photo_id = a.photo_id AND earlier.reviewer = a.reviewer
        AND earlier.id < a.id
    )
    AND NOT EXISTS (
        SELECT 1 FROM reviews r WHERE r.run_id = a.run_id AND r.photo_id = a.photo_id
        AND r.created_at <= a.created_at AND NOT EXISTS (
            SELECT 1 FROM audits own WHERE own.run_id = r.run_id
            AND own.photo_id = r.photo_id AND own.reviewer = r.reviewer
            AND own.created_at < r.created_at
        )
    )
) = ?
ORDER BY a.id
"""


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
                CREATE TABLE IF NOT EXISTS audits (
                    id INTEGER PRIMARY KEY, run_id TEXT NOT NULL, photo_id TEXT NOT NULL,
                    finding TEXT NOT NULL, note TEXT NOT NULL, reviewer TEXT NOT NULL,
                    effort_seconds REAL, created_at TEXT NOT NULL,
                    FOREIGN KEY(run_id, photo_id) REFERENCES photos(run_id, id)
                );
                CREATE TABLE IF NOT EXISTS findings (
                    id INTEGER PRIMARY KEY, run_id TEXT NOT NULL, photo_id TEXT NOT NULL,
                    kind TEXT NOT NULL, species TEXT, other_taxon TEXT, box TEXT,
                    note TEXT NOT NULL, reviewer TEXT NOT NULL, effort_seconds REAL,
                    created_at TEXT NOT NULL,
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
        findings: dict[str, list[dict]] = {}
        for item in self.findings(run_id):
            findings.setdefault(item["photo_id"], []).append(item)
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
                findings=findings.get(row["id"], []),
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

    def audit(
        self,
        run_id: str,
        photo_id: str,
        finding: str,
        note: str,
        reviewer: str,
        effort_seconds: float | None = None,
    ) -> None:
        with self.connect() as db:
            exists = db.execute(
                "SELECT 1 FROM photos WHERE run_id=? AND id=?", (run_id, photo_id)
            ).fetchone()
            if exists is None:
                raise KeyError(photo_id)
            db.execute(
                "INSERT INTO audits(run_id,photo_id,finding,note,reviewer,effort_seconds,"
                "created_at) VALUES(?,?,?,?,?,?,?)",
                (run_id, photo_id, finding, note, reviewer, effort_seconds, now()),
            )

    def audits(self, run_id: str, photo_id: str) -> list[dict]:
        with self.connect() as db:
            return [
                dict(row)
                for row in db.execute(
                    "SELECT * FROM audits WHERE run_id=? AND photo_id=? ORDER BY id",
                    (run_id, photo_id),
                )
            ]

    def latest_audits(self, run_id: str, blind: bool = True) -> dict[str, dict[str, str]]:
        """Each auditor's latest blind (or, with `blind=False`, later) finding per photo."""
        with self.connect() as db:
            rows = db.execute(AUDITS_BY_BLINDNESS, (run_id, blind)).fetchall()
        findings: dict[str, dict[str, str]] = {}
        for row in rows:
            findings.setdefault(row["photo_id"], {})[row["reviewer"]] = row["finding"]
        return findings

    def finding(self, run_id: str, photo_id: str, record: Finding) -> None:
        """Append a reviewer's finding; findings are never edited or deleted."""
        box = json.dumps(list(record.box)) if record.box else None
        with self.connect() as db:
            db.execute(
                "INSERT INTO findings(run_id,photo_id,kind,species,other_taxon,box,note,"
                "reviewer,effort_seconds,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
                (
                    run_id,
                    photo_id,
                    record.kind,
                    record.species,
                    record.other_taxon,
                    box,
                    record.note,
                    record.reviewer,
                    record.effort_seconds,
                    now(),
                ),
            )

    def findings(self, run_id: str, photo_id: str | None = None) -> list[dict]:
        query = "SELECT * FROM findings WHERE run_id=?"
        parameters: tuple[str, ...] = (run_id,)
        if photo_id is not None:
            query, parameters = f"{query} AND photo_id=?", (run_id, photo_id)
        with self.connect() as db:
            rows = db.execute(f"{query} ORDER BY id", parameters).fetchall()
        return [dict(row, box=row["box"] and json.loads(row["box"])) for row in rows]
