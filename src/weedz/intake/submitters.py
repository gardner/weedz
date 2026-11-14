"""Submitter tokens: the devices allowed to send reports (issue #57).

A submitter is a device install, a different principal from a reviewer (#31): its token
is ``weedzsub_<id>_<secret>``, never accepted by the review API, and a reviewer token is
never accepted here. Only the secret's SHA-256 is kept, in ``submitters.sqlite3`` beside
(never inside) the reports, so a copy of the reports carries no credentials. The label
is the operator's note of whose device it is; it is not sent with reports.
"""

import sqlite3
from collections.abc import Callable
from contextlib import closing
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from fastapi import HTTPException, Request

from weedz import tokens

PREFIX = "weedzsub"
SCHEMA = """
CREATE TABLE IF NOT EXISTS submitter_tokens(
    id INTEGER PRIMARY KEY AUTOINCREMENT, label TEXT NOT NULL,
    secret_sha256 TEXT NOT NULL, created_at TEXT NOT NULL, revoked_at TEXT
);
"""


@dataclass(frozen=True)
class Credential:
    id: int
    label: str
    token: str = field(repr=False)


class Submitters:
    def __init__(self, root: Path) -> None:
        self.path = root / "submitters.sqlite3"

    def _connect(self) -> sqlite3.Connection:
        return tokens.connect_private(self.path, SCHEMA)

    def issue(self, label: str) -> Credential:
        label = label.strip()
        if not 0 < len(label) <= 80:
            raise ValueError("A submitter label needs 1 to 80 characters")
        secret = tokens.new_secret()
        with closing(self._connect()) as db, db:
            cursor = db.execute(
                "INSERT INTO submitter_tokens(label,secret_sha256,created_at) VALUES(?,?,?)",
                (label, tokens.digest(secret), datetime.now(UTC).isoformat()),
            )
        token_id = cursor.lastrowid
        assert token_id is not None
        return Credential(token_id, label, f"{PREFIX}_{token_id}_{secret}")

    def revoke(self, token_id: int) -> bool:
        """Revoke an active submitter; False when there is none with that id."""
        with closing(self._connect()) as db, db:
            cursor = db.execute(
                "UPDATE submitter_tokens SET revoked_at=? WHERE id=? AND revoked_at IS NULL",
                (datetime.now(UTC).isoformat(), token_id),
            )
        return cursor.rowcount == 1

    def listing(self) -> list[dict]:
        """Every submitter issued, without its token or hash."""
        with closing(self._connect()) as db:
            rows = db.execute(
                "SELECT id,label,created_at,revoked_at FROM submitter_tokens ORDER BY id"
            ).fetchall()
        return [dict(row) for row in rows]

    def submitter(self, token: str, *, allow_revoked: bool = False) -> int | None:
        """The id of the active submitter a token names, or None."""
        parts = tokens.split(token, PREFIX)
        if parts is None:
            return None
        token_id, secret = parts
        with closing(self._connect()) as db:
            row = db.execute(
                "SELECT secret_sha256 FROM submitter_tokens WHERE id=? "
                "AND (revoked_at IS NULL OR ?)",
                (token_id, allow_revoked),
            ).fetchone()
        return token_id if tokens.matches(secret, row["secret_sha256"] if row else None) else None


def require_submitter(
    store: Submitters, *, allow_revoked: bool = False
) -> Callable[[Request], None]:
    """A request dependency: the bearer token of an active submitter, whose id it puts in
    ``request.state.submitter``. Sync, so FastAPI runs its SQLite lookup off the loop."""

    def dependency(request: Request) -> None:
        token = tokens.bearer(request)
        submitter = store.submitter(token, allow_revoked=allow_revoked) if token else None
        if submitter is None:
            raise HTTPException(
                401, "Send a submitter token", headers={"WWW-Authenticate": "Bearer"}
            )
        request.state.submitter = submitter

    return dependency
