"""SQLite review store; idempotent activities never overwrite human decisions."""

import json
import sqlite3
from collections import Counter
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from weedz.discovery.judgements import Judgement, judged, standing_judgements
from weedz.discovery.leads import TABLE as LEAD_TABLE
from weedz.discovery.records import Finding, Photo, RunSpec
from weedz.discovery.referrals import TABLES as REFERRAL_TABLES
from weedz.discovery.referrals import Referral, ReferralEvent, with_status
from weedz.discovery.sharing import refuse_unadmitted
from weedz.discovery.study import TABLES as STUDY_TABLES


def now() -> str:
    return datetime.now(UTC).isoformat()


def add_missing_column(
    db: sqlite3.Connection, table: str, column: str, definition: str = "TEXT NOT NULL DEFAULT ''"
) -> None:
    if column not in {row["name"] for row in db.execute(f"PRAGMA table_info({table})")}:
        db.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


def finding_row(row: sqlite3.Row) -> dict[str, Any]:
    return dict(row, box=row["box"] and json.loads(row["box"]))


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
# photo is released into their ranked queue) and no one reviewed the photo, or recorded a
# finding, judgement, referral or lead selection on it (or answered a referral), before
# it without having audited it first. The app lets a sampled photo be reviewed only after
# the reviewer's own audit, so any other earlier review, finding, judgement, referral or
# selection, such as one made before the sample existed, means the suggestion may have
# been seen.
AUDITS_BY_BLINDNESS = """
SELECT a.photo_id, a.reviewer, a.finding FROM audits a
WHERE a.run_id = ? AND (
    NOT EXISTS (
        SELECT 1 FROM audits earlier WHERE earlier.run_id = a.run_id
        AND earlier.photo_id = a.photo_id AND earlier.reviewer = a.reviewer
        AND earlier.id < a.id
    )
    AND NOT EXISTS (
        SELECT 1 FROM (
            SELECT run_id, photo_id, reviewer, created_at FROM reviews
            UNION ALL SELECT run_id, photo_id, reviewer, created_at FROM findings
            UNION ALL SELECT run_id, photo_id, reviewer, created_at FROM judgements
            UNION ALL SELECT run_id, photo_id, referrer, created_at FROM referrals
            UNION ALL SELECT f.run_id, f.photo_id, e.actor, e.created_at
            FROM referral_events e JOIN referrals f ON f.id = e.referral_id
            UNION ALL SELECT run_id, photo_id, selector, created_at FROM lead_selections
        ) r WHERE r.run_id = a.run_id AND r.photo_id = a.photo_id
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
                CREATE TABLE IF NOT EXISTS judgements (
                    id INTEGER PRIMARY KEY, run_id TEXT NOT NULL, photo_id TEXT NOT NULL,
                    finding_id INTEGER REFERENCES findings(id),
                    dimension TEXT NOT NULL, value TEXT NOT NULL, note TEXT NOT NULL,
                    reviewer TEXT NOT NULL, effort_seconds REAL, created_at TEXT NOT NULL,
                    reference_snapshot TEXT,
                    FOREIGN KEY(run_id, photo_id) REFERENCES photos(run_id, id)
                );
            """)
            db.executescript(REFERRAL_TABLES)
            db.executescript(LEAD_TABLE)
            db.executescript(STUDY_TABLES)
            # Databases created before reviewer attribution keep their history unattributed.
            add_missing_column(db, "photos", "review_reviewer")
            add_missing_column(db, "reviews", "reviewer")
            # Earlier decisions were not timed: NULL means unmeasured, never zero effort.
            add_missing_column(db, "reviews", "effort_seconds", "REAL")
            # When each photo was last scored; NULL before this was recorded or before screening.
            add_missing_column(db, "photos", "screened_at", "TEXT")

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
            db.execute(
                "UPDATE runs SET status=?, detail=? WHERE id=? "
                "AND status NOT IN ('completed', 'failed')",
                (status, detail, run_id),
            )

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
        """Save acquired photos; any source's photo under a licence not admitted is refused."""
        for photo in photos:
            refuse_unadmitted(photo.photo_license, photo.observation_license)
        with self.connect() as db:
            db.executemany(
                "INSERT INTO photos(run_id,id,record) VALUES(?,?,?) "
                "ON CONFLICT(run_id,id) DO UPDATE SET record=excluded.record",
                [(run_id, photo.id, photo.model_dump_json()) for photo in photos],
            )

    def photos(self, run_id: str) -> list[dict[str, Any]]:
        with self.connect() as db:
            return self._photos(db, run_id)

    @staticmethod
    def _photos(db: sqlite3.Connection, run_id: str) -> list[dict[str, Any]]:
        """Read through the caller's transaction, including a read-only export snapshot."""
        rows = db.execute("SELECT * FROM photos WHERE run_id=? ORDER BY id", (run_id,)).fetchall()
        events = db.execute(
            "SELECT photo_id, reviewer, status FROM reviews WHERE run_id=? ORDER BY id",
            (run_id,),
        ).fetchall()
        recorded = db.execute(
            "SELECT * FROM findings WHERE run_id=? ORDER BY id", (run_id,)
        ).fetchall()
        judgements = db.execute(
            "SELECT * FROM judgements WHERE run_id=? ORDER BY id", (run_id,)
        ).fetchall()
        referred = Store._referrals(db, run_id)

        referrals: dict[str, list[dict]] = {}
        for item in referred:
            referrals.setdefault(item["photo_id"], []).append(item)
        decisions = reviewer_decisions(events)
        standing = standing_judgements(judgements)
        counts = Counter(event["photo_id"] for event in events)
        findings: dict[str, list[dict]] = {}
        for row in recorded:
            plant = finding_row(row) | judged(standing, (row["photo_id"], row["id"]))
            findings.setdefault(row["photo_id"], []).append(plant)
        return [
            dict(
                json.loads(row["record"]),
                scores=json.loads(row["scores"]),
                screened_at=row["screened_at"],
                review_status=row["review_status"],
                review_note=row["review_note"],
                review_reviewer=row["review_reviewer"],
                reviewer_decisions=decisions.get(row["id"], {}),
                disputed=len(set(decisions.get(row["id"], {}).values())) > 1,
                review_count=counts[row["id"]],
                findings=findings.get(row["id"], []),
                referrals=referrals.get(row["id"], []),
                **judged(standing, (row["id"], None)),
            )
            for row in rows
        ]

    def score(self, run_id: str, photo_id: str, scores: dict) -> None:
        with self.connect() as db:
            db.execute(
                "UPDATE photos SET scores=CASE "
                "WHEN json_type(scores, '$.segmentation') IS NOT NULL "
                "THEN json_set(?, '$.segmentation', json_extract(scores, '$.segmentation')) "
                "ELSE ? END, screened_at=? WHERE run_id=? AND id=?",
                (json.dumps(scores), json.dumps(scores), now(), run_id, photo_id),
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

    def findings(self, run_id: str, photo_id: str) -> list[dict]:
        with self.connect() as db:
            rows = db.execute(
                "SELECT * FROM findings WHERE run_id=? AND photo_id=? ORDER BY id",
                (run_id, photo_id),
            ).fetchall()
        return [finding_row(row) for row in rows]

    def judgement(
        self, run_id: str, photo_id: str, record: Judgement, reference_snapshot: str | None = None
    ) -> None:
        """Append a reviewer's judgement on one dimension; never edited or deleted.
        `reference_snapshot` is the SHA-256 of the reference records it was made against."""
        with self.connect() as db:
            db.execute(
                "INSERT INTO judgements(run_id,photo_id,finding_id,dimension,value,note,"
                "reviewer,effort_seconds,created_at,reference_snapshot) "
                "VALUES(?,?,?,?,?,?,?,?,?,?)",
                (
                    run_id,
                    photo_id,
                    record.finding_id,
                    record.dimension,
                    record.value,
                    record.note,
                    record.reviewer,
                    record.effort_seconds,
                    now(),
                    reference_snapshot,
                ),
            )

    def judgements(self, run_id: str, photo_id: str) -> list[dict]:
        with self.connect() as db:
            return [
                dict(row)
                for row in db.execute(
                    "SELECT * FROM judgements WHERE run_id=? AND photo_id=? ORDER BY id",
                    (run_id, photo_id),
                )
            ]

    @staticmethod
    def _referrals(
        db: sqlite3.Connection, run_id: str, photo_id: str | None = None
    ) -> list[dict[str, Any]]:
        """A run's referrals (or one photo's), oldest first, with status and events."""
        where = "r.run_id=?" + (" AND r.photo_id=?" if photo_id else "")
        values = (run_id, photo_id) if photo_id else (run_id,)
        rows = db.execute(f"SELECT * FROM referrals r WHERE {where} ORDER BY id", values)
        events: dict[int, list[dict]] = {}
        for event in db.execute(
            "SELECT e.* FROM referral_events e JOIN referrals r ON r.id = e.referral_id "
            f"WHERE {where} ORDER BY e.id",
            values,
        ):
            cited = json.loads(event["judgement_ids"])
            events.setdefault(event["referral_id"], []).append(dict(event, judgement_ids=cited))
        return [with_status(dict(row), events.get(row["id"], [])) for row in rows]

    def referrals(self, run_id: str, photo_id: str) -> list[dict]:
        with self.connect() as db:
            return self._referrals(db, run_id, photo_id)

    def refer(self, run_id: str, photo_id: str, record: Referral) -> int:
        """Open a referral for specialist assessment; returns its id."""
        with self.connect() as db:
            cursor = db.execute(
                "INSERT INTO referrals(run_id,photo_id,finding_id,reason,expertise,note,"
                "referrer,effort_seconds,created_at) VALUES(?,?,?,?,?,?,?,?,?)",
                (
                    run_id,
                    photo_id,
                    record.finding_id,
                    record.reason,
                    record.expertise,
                    record.note,
                    record.referrer,
                    record.effort_seconds,
                    now(),
                ),
            )
            return cursor.lastrowid or 0

    def close_referral(
        self, run_id: str, photo_id: str, referral_id: int, event: ReferralEvent
    ) -> None:
        """Answer or withdraw an open referral of this photo. The insert itself checks the
        referral is still open, so two closes at once cannot both succeed."""
        with self.connect() as db:
            cursor = db.execute(
                "INSERT INTO referral_events(referral_id,action,actor,note,judgement_ids,"
                "effort_seconds,created_at) SELECT id,?,?,?,?,?,? FROM referrals "
                "WHERE id=? AND run_id=? AND photo_id=? AND NOT EXISTS "
                "(SELECT 1 FROM referral_events WHERE referral_id=referrals.id)",
                (
                    event.action,
                    event.actor,
                    event.note,
                    json.dumps(event.judgement_ids),
                    event.effort_seconds,
                    now(),
                    referral_id,
                    run_id,
                    photo_id,
                ),
            )
            if cursor.rowcount:
                return
            found = next(
                (
                    item
                    for item in self._referrals(db, run_id, photo_id)
                    if item["id"] == referral_id
                ),
                None,
            )
        if found is None:
            raise KeyError(referral_id)
        raise ValueError(f"This referral is already {found['status']}")
