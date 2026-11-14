"""Reviewer invite tokens for remote review (issue #31).

A token is ``weedz_<id>_<secret>`` (see weedz.tokens). Only the SHA-256 of the secret is
kept, in ``access.sqlite3`` beside (never inside) the discovery store, so a copied store
carries no credentials.
"""

import sqlite3
from collections.abc import Awaitable, Callable
from contextlib import closing, suppress
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from fastapi import HTTPException, Request
from pydantic import TypeAdapter, ValidationError

from weedz import tokens
from weedz.discovery.records import ReviewerName

PREFIX = "weedz"
# The body field that names who makes each kind of record. In tokens mode it must be the
# signed-in reviewer (tests check every attributed write is listed here).
ATTRIBUTION_FIELDS = frozenset({"reviewer", "author", "linked_by", "selector", "referrer", "actor"})
SCHEMA = """
CREATE TABLE IF NOT EXISTS reviewer_tokens(
    id INTEGER PRIMARY KEY AUTOINCREMENT, reviewer TEXT NOT NULL,
    secret_sha256 TEXT NOT NULL, created_at TEXT NOT NULL, revoked_at TEXT
);
"""
_NAME = TypeAdapter(ReviewerName)


@dataclass(frozen=True)
class Invite:
    id: int
    reviewer: str
    token: str = field(repr=False)


class Access:
    def __init__(self, root: Path) -> None:
        self.path = root / "access.sqlite3"

    def _connect(self) -> sqlite3.Connection:
        return tokens.connect_private(self.path, SCHEMA)

    def invite(self, reviewer: str) -> Invite:
        try:
            name = _NAME.validate_python(reviewer)
        except ValidationError as error:
            raise ValueError("A reviewer name needs 1 to 80 characters") from error
        secret = tokens.new_secret()
        created = datetime.now(UTC).isoformat()
        with closing(self._connect()) as db, db:
            cursor = db.execute(
                "INSERT INTO reviewer_tokens(reviewer,secret_sha256,created_at) VALUES(?,?,?)",
                (name, tokens.digest(secret), created),
            )
        token_id = cursor.lastrowid
        assert token_id is not None
        return Invite(token_id, name, f"{PREFIX}_{token_id}_{secret}")

    def revoke(self, token_id: int) -> bool:
        """Revoke an active invite; False when there is none with that id."""
        with closing(self._connect()) as db, db:
            cursor = db.execute(
                "UPDATE reviewer_tokens SET revoked_at=? WHERE id=? AND revoked_at IS NULL",
                (datetime.now(UTC).isoformat(), token_id),
            )
        return cursor.rowcount == 1

    def reviewers(self) -> list[dict]:
        """Every invite issued, without its token or hash."""
        with closing(self._connect()) as db:
            rows = db.execute(
                "SELECT id,reviewer,created_at,revoked_at FROM reviewer_tokens ORDER BY id"
            ).fetchall()
        return [dict(row) for row in rows]

    def reviewer(self, token: str) -> str | None:
        """The reviewer an active token names, or None."""
        parts = tokens.split(token, PREFIX)
        if parts is None:
            return None
        token_id, secret = parts
        with closing(self._connect()) as db:
            row = db.execute(
                "SELECT reviewer,secret_sha256 FROM reviewer_tokens "
                "WHERE id=? AND revoked_at IS NULL",
                (token_id,),
            ).fetchone()
        # Compared even when the id is unknown, so timing does not reveal which ids exist.
        matched = tokens.matches(secret, row["secret_sha256"] if row else None)
        return row["reviewer"] if row and matched else None


def require_reviewer(store: Access) -> Callable[[Request], Awaitable[None]]:
    """A request dependency for tokens mode: a bearer token naming an active reviewer, who
    must also be the one any record in the body is attributed to."""

    async def dependency(request: Request) -> None:
        token = tokens.bearer(request)
        reviewer = store.reviewer(token) if token else None
        if reviewer is None:
            raise HTTPException(
                401, "Sign in with your reviewer token", headers={"WWW-Authenticate": "Bearer"}
            )
        request.state.reviewer = reviewer
        if await _attributed_to(request) - {reviewer}:
            raise HTTPException(403, f"Signed in as {reviewer}; record under that name")

    return dependency


async def _attributed_to(request: Request) -> set[str]:
    """The names a write's body attributes it to; validation reports anything malformed."""
    if request.method != "POST":
        return set()
    try:
        body = await request.json()
    except ValueError:
        return set()
    if not isinstance(body, dict):
        return set()
    names = set()
    for key in ATTRIBUTION_FIELDS & body.keys():
        # Normalise exactly as the record model will, so the name checked is the one stored.
        # (str.strip removes more characters than the model's strip_whitespace.)
        with suppress(ValidationError):  # an invalid name fails the route's own validation
            names.add(_NAME.validate_python(body[key]))
    return names


def session(request: Request) -> dict[str, str]:
    """How this API is run, and who is signed in. Never echoes the token."""
    reviewer = getattr(request.state, "reviewer", None)
    return {"mode": "tokens", "reviewer": reviewer} if reviewer else {"mode": "local"}
