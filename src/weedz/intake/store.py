"""Where received reports are kept: apart from the discovery evidence, never published.

``reports/reports.sqlite3`` holds each report under its submitter and device-chosen id;
cleaned crops sit in ``reports/images`` under random names. Both are owner-only.
Withdrawing a report deletes its image and erases its content, leaving a tombstone of ids,
times and what was agreed (the consent wording and permitted uses, never the credit name)
so a retry cannot bring it back and the history shows when consent ended (#60).
``secure_delete`` zeroes the erased content in the database file too. ``active()`` is
where specialist review would read reports (#58).
"""

import json
import os
import sqlite3
import uuid
from collections.abc import Iterator
from contextlib import closing, contextmanager
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from pathlib import Path

from weedz import tokens
from weedz.intake import budget
from weedz.intake.deletion import SCHEMA as DELETION_SCHEMA
from weedz.intake.deletion import is_deleting
from weedz.intake.limits import Limits
from weedz.intake.schema import Report, ReportContent

SCHEMA = (
    """
CREATE TABLE IF NOT EXISTS reports(
    submitter INTEGER NOT NULL, report_id TEXT NOT NULL, received_at TEXT NOT NULL,
    content_sha256 TEXT, body TEXT, image_file TEXT, withdrawn_at TEXT, consent TEXT,
    PRIMARY KEY(submitter, report_id)
);
"""
    + budget.SCHEMA
    + DELETION_SCHEMA
)


class Withdrawn(Exception):
    """The report id was withdrawn; it is not received again."""


class Conflict(Exception):
    """The report id was already received with different content."""


@dataclass(frozen=True)
class Receipt:
    report_id: str
    status: str
    received_at: str
    withdrawn_at: str | None
    image: bool
    # What the person agreed to, kept after withdrawal: the wording and the photo's uses.
    # None and [] for an id withdrawn before it arrived, or stored before consent was
    # recorded (#60).
    consent_version: str | None
    uses: list[str]

    @classmethod
    def of(cls, row: sqlite3.Row) -> "Receipt":
        status = "withdrawn" if row["withdrawn_at"] else "received"
        image = row["image_file"] is not None
        agreed = json.loads(row["consent"] or '{"version": null, "uses": []}')
        return cls(
            row["report_id"],
            status,
            row["received_at"],
            row["withdrawn_at"],
            image,
            agreed["version"],
            agreed["uses"],
        )


@dataclass(frozen=True)
class StoredReport:
    submitter: int
    report_id: str
    received_at: str
    report: ReportContent
    image: Path | None


class ReportStore:
    def __init__(self, root: Path) -> None:
        self.folder = root / "reports"
        self.images = self.folder / "images"
        self.path = self.folder / "reports.sqlite3"

    def _connect(self) -> sqlite3.Connection:
        for folder in (self.folder, self.images):
            folder.mkdir(mode=0o700, parents=True, exist_ok=True)
        db = tokens.connect_private(self.path, SCHEMA)
        db.execute("PRAGMA secure_delete=ON")
        if not _records_consent(db):
            _record_consent(db)
        return db

    @contextmanager
    def _transaction(self) -> Iterator[sqlite3.Connection]:
        with closing(self._connect()) as db:
            db.execute("BEGIN IMMEDIATE")  # one writer decides each id and budget
            try:
                yield db
            except BaseException:
                db.rollback()
                raise
            db.commit()

    def receipt(self, submitter: int, report_id: str) -> Receipt | None:
        """A submitter's own receipt for an id, or None."""
        with closing(self._connect()) as db:
            return _existing(db, submitter, report_id, None)

    def admit(
        self, submitter: int, report_id: str, digest: str, has_image: bool, limits: Limits
    ) -> Receipt | None:
        """Before any image work: the receipt when this is a retry, or None when it is new,
        having charged it to the submitter's budget. Raises Withdrawn, Conflict or
        OverBudget. ``receive`` then charges the stored crop's exact size."""
        with self._transaction() as db:
            if is_deleting(db, submitter):
                raise Withdrawn
            earlier = _existing(db, submitter, report_id, digest)
            if earlier is None:
                budget.charge(db, submitter, report_id, has_image, limits)
            return earlier

    def receive(
        self,
        submitter: int,
        report_id: str,
        report: Report,
        digest: str,
        image: bytes | None,
        limits: Limits,
    ) -> tuple[Receipt, bool]:
        """Store a report that ``admit`` charged (True), or return the receipt of the same
        one received before (False). Raises Withdrawn, Conflict or OverBudget."""
        name = None
        try:
            with self._transaction() as db:
                if is_deleting(db, submitter):
                    raise Withdrawn
                existing = _existing(db, submitter, report_id, digest)
                if existing:
                    return existing, False
                budget.settle(db, submitter, report_id, len(image or b""), limits)
                received = _now()
                name = self._write_image(image) if image else None
                content = report.model_dump_json(exclude={"image"})
                row = (submitter, report_id, received, digest, content, name, agreed(report))
                db.execute(
                    "INSERT INTO reports(submitter, report_id, received_at, content_sha256, "
                    "body, image_file, consent) VALUES(?,?,?,?,?,?,?)",
                    row,
                )
        except BaseException:
            # Not committed, so no image is left behind without its report.
            if name:
                (self.images / name).unlink(missing_ok=True)
            raise
        uses: list[str] = sorted(report.consent.uses)
        version = report.consent.wording_version
        return Receipt(report_id, "received", received, None, bool(name), version, uses), True

    def withdraw(
        self,
        submitter: int,
        report_id: str,
        before_arrival: bool = False,
        limits: Limits | None = None,
    ) -> Receipt | None:
        """Delete the image and erase the content of a submitter's own report. With
        ``before_arrival``, an id not yet received is recorded as withdrawn, so a report
        still on its way is refused when it arrives. Both the device API and the operator
        can record this intent before an upload arrives."""
        with self._transaction() as db:
            if is_deleting(db, submitter):
                raise Withdrawn
            row = _row(db, submitter, report_id)
            if row is None and before_arrival:
                # Device-created tombstones cost a new record; trusted operators may
                # bypass the budget. Existing withdrawals and retries never cost.
                if limits is not None:
                    budget.charge(db, submitter, report_id, False, limits)
                now = _now()
                # Never received, so nothing was agreed: no consent is recorded.
                db.execute(
                    "INSERT INTO reports(submitter, report_id, received_at, withdrawn_at) "
                    "VALUES(?,?,?,?)",
                    (submitter, report_id, now, now),
                )
                return Receipt(report_id, "withdrawn", now, now, False, None, [])
            if row is None:
                return None
            if row["image_file"]:
                (self.images / row["image_file"]).unlink(missing_ok=True)
                self._sync_images()  # the deletion is durable before the withdrawal commits
            withdrawn = row["withdrawn_at"] or _now()
            db.execute(
                "UPDATE reports SET withdrawn_at=?, body=NULL, content_sha256=NULL, "
                "image_file=NULL WHERE submitter=? AND report_id=?",
                (withdrawn, submitter, report_id),
            )
            return replace(Receipt.of(row), status="withdrawn", withdrawn_at=withdrawn, image=False)

    def active(self) -> list[StoredReport]:
        """Materialize a specialist snapshot before a deletion marker can commit.

        Already-returned snapshots cannot be revoked; callers must not cache report
        content past its use or treat an old snapshot as current withdrawal state.
        """
        with closing(self._connect()) as db, db:
            # SELECT alone is autocommit: fetchall would release its read lock before
            # parsing. An explicit read transaction orders this call before erasure.
            db.execute("BEGIN")
            rows = db.execute(
                "SELECT * FROM reports WHERE withdrawn_at IS NULL AND submitter NOT IN "
                "(SELECT submitter FROM submitter_deletions) ORDER BY received_at"
            ).fetchall()
            return [
                StoredReport(
                    row["submitter"],
                    row["report_id"],
                    row["received_at"],
                    ReportContent.model_validate_json(row["body"], context={"stored": True}),
                    self._image(row["image_file"]),
                )
                for row in rows
            ]

    def sweep(self) -> None:
        """Delete orphan crops under the upload writer lock, including while workers run."""
        with self._transaction() as db:
            self._sweep(db)

    def _sweep(self, db: sqlite3.Connection) -> None:
        """Sweep within the caller's existing write transaction; never nest transactions.

        Every normal image write holds that same transaction until its report commits,
        so an unreferenced crop here belongs to an interrupted upload, not a live one.
        """
        named = {row[0] for row in db.execute("SELECT image_file FROM reports")}
        for path in self.images.iterdir():
            if path.name not in named:
                path.unlink(missing_ok=True)
        self._sync_images()

    def _image(self, name: str | None) -> Path | None:
        # Withdrawal deletes the file before erasing the row (privacy first), so a failed
        # commit can leave a row naming a deleted image: that report has no image.
        path = self.images / name if name else None
        return path if path and path.exists() else None

    def _write_image(self, image: bytes) -> str:
        name = f"{uuid.uuid4().hex}.jpg"
        descriptor = os.open(self.images / name, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        with os.fdopen(descriptor, "wb") as out:
            out.write(image)
            out.flush()
            os.fsync(out.fileno())
        # Durable before the report naming it commits, so a 201 never names a lost crop.
        self._sync_images()
        return name

    def _sync_images(self) -> None:
        """Make files written to, or deleted from, the images folder survive a power cut."""
        folder = os.open(self.images, os.O_RDONLY)
        try:
            os.fsync(folder)
        finally:
            os.close(folder)


def _records_consent(db: sqlite3.Connection) -> bool:
    return any(row["name"] == "consent" for row in db.execute("PRAGMA table_info(reports)"))


def _record_consent(db: sqlite3.Connection) -> None:
    """Upgrade a store made before consent was recorded (#60). A photo was then sent for
    review alone, so its report is read as permitting review and nothing more. A location
    was sent only as part of the report its person approved, so a located report is read
    as consenting to share that point (#91)."""
    db.execute("BEGIN IMMEDIATE")  # another connection may be upgrading it too
    if _records_consent(db):
        db.rollback()
        return
    db.execute("ALTER TABLE reports ADD COLUMN consent TEXT")
    rows = db.execute("SELECT rowid, body FROM reports WHERE body IS NOT NULL").fetchall()
    for row in rows:
        body = json.loads(row["body"])
        consent = body["consent"]
        consent.setdefault("uses", ["review"] if consent.get("image") else [])
        consent.setdefault("location", body.get("location") is not None)
        agreed = json.dumps({"version": consent["wording_version"], "uses": consent["uses"]})
        db.execute(
            "UPDATE reports SET body=?, consent=? WHERE rowid=?",
            (json.dumps(body), agreed, row["rowid"]),
        )
    db.commit()


def agreed(report: ReportContent) -> str:
    """The non-identifying record of what was agreed: kept even after withdrawal."""
    consent = report.consent
    return json.dumps({"version": consent.wording_version, "uses": sorted(consent.uses)})


def _row(db: sqlite3.Connection, submitter: int, report_id: str) -> sqlite3.Row | None:
    return db.execute(
        "SELECT * FROM reports WHERE submitter=? AND report_id=?", (submitter, report_id)
    ).fetchone()


def _existing(
    db: sqlite3.Connection, submitter: int, report_id: str, digest: str | None
) -> Receipt | None:
    row = _row(db, submitter, report_id)
    if row is None or digest is None:
        return Receipt.of(row) if row else None
    if row["withdrawn_at"]:
        raise Withdrawn
    if row["content_sha256"] != digest:
        raise Conflict
    return Receipt.of(row)


def _now() -> str:
    return budget.stamp(datetime.now(UTC))
