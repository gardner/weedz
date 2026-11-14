"""Each submitter's rolling 24-hour budget of new reports and stored image bytes.

Usage is kept apart from the reports, one row per new report the server works on:
charged before any image is decoded, whether or not the report is then stored, so a
refused decode still costs the submitter. Withdrawing a report does not refund it. A
row holds only the submitter, report id, time and stored crop size, and rows are deleted
once they leave the window, so a crop's size is not kept past the time it is needed.
"""

import sqlite3
from datetime import UTC, datetime, timedelta

from weedz.intake.limits import DAY_SECONDS, Limits

SCHEMA = """
CREATE TABLE IF NOT EXISTS usage(
    submitter INTEGER NOT NULL, report_id TEXT NOT NULL, used_at TEXT NOT NULL,
    image_bytes INTEGER NOT NULL DEFAULT 0
);
"""


class OverBudget(Exception):
    def __init__(self, retry_after: int) -> None:
        super().__init__(f"Daily budget used; retry after {retry_after} seconds")
        self.retry_after = retry_after


_DAY = timedelta(seconds=DAY_SECONDS)


def charge(
    db: sqlite3.Connection, submitter: int, report_id: str, image: bool, limits: Limits
) -> None:
    """Record a new report before any image work, or raise OverBudget. The crop's size is
    unknown until it is cleaned, so here a crop counts as one byte."""
    _refuse_unless_fits(_window(db, submitter, None), int(image), limits)
    db.execute(
        "INSERT INTO usage(submitter, report_id, used_at) VALUES(?,?,?)",
        (submitter, report_id, stamp(datetime.now(UTC))),
    )


def settle(
    db: sqlite3.Connection, submitter: int, report_id: str, image_bytes: int, limits: Limits
) -> None:
    """Charge a charged report its stored crop's exact size, or raise OverBudget."""
    (latest,) = db.execute(
        "SELECT MAX(rowid) FROM usage WHERE submitter=? AND report_id=?", (submitter, report_id)
    ).fetchone()
    _refuse_unless_fits(_window(db, submitter, latest), image_bytes, limits)
    db.execute("UPDATE usage SET image_bytes=? WHERE rowid=?", (image_bytes, latest))


def _window(db: sqlite3.Connection, submitter: int, leaving_out: int | None) -> list[sqlite3.Row]:
    """A submitter's usage in the last 24 hours, oldest first, after deleting all older
    usage. ``leaving_out`` is the charge being settled, which is counted as the new one."""
    db.execute("DELETE FROM usage WHERE used_at<=?", (stamp(_now() - _DAY),))
    return db.execute(
        "SELECT used_at, image_bytes FROM usage WHERE submitter=? AND rowid IS NOT ? "
        "ORDER BY used_at",
        (submitter, leaving_out),
    ).fetchall()


def _refuse_unless_fits(rows: list[sqlite3.Row], image_bytes: int, limits: Limits) -> None:
    """Raise OverBudget, saying when enough of the window will have expired for one more
    report with ``image_bytes`` to fit."""
    count, used = len(rows), sum(row["image_bytes"] for row in rows)

    def fits() -> bool:
        return (
            count + 1 <= limits.reports_per_day and used + image_bytes <= limits.image_bytes_per_day
        )

    if fits():
        return
    wait = _DAY  # if nothing expiring makes room: a whole day
    for row in rows:
        count, used = count - 1, used - row["image_bytes"]
        if fits():
            wait = datetime.fromisoformat(row["used_at"]) + _DAY - _now()
            break
    raise OverBudget(max(1, int(wait.total_seconds()) + 1))


def _now() -> datetime:
    return datetime.now(UTC)


def stamp(when: datetime) -> str:
    # A fixed width, so stored times compare in order as text.
    return when.isoformat(timespec="microseconds")
