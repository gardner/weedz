"""Bearer tokens shared by every kind of principal (reviewers #31, submitting devices #57).

A token is ``<prefix>_<id>_<secret>``: 256 random bits, shown once when issued. Only the
SHA-256 of the secret is kept. A fast hash suits a long random secret; slow password
hashes are for secrets people choose. Each principal has its own prefix, so one kind of
token is never accepted as another.
"""

import hashlib
import hmac
import os
import secrets
import sqlite3
from pathlib import Path

from fastapi import Request

# Compared against when the id is unknown, so a miss costs the same as a wrong secret.
ABSENT = hashlib.sha256(b"no such token").hexdigest()


def digest(secret: str) -> str:
    return hashlib.sha256(secret.encode()).hexdigest()


def new_secret() -> str:
    return secrets.token_urlsafe(32)


def split(token: str, prefix: str) -> tuple[int, str] | None:
    """The id and secret of a token with this prefix, or None for any other string."""
    found, _, rest = token.partition("_")
    token_id, _, secret = rest.partition("_")
    # At most 18 digits, so the id always fits SQLite's 64-bit integer.
    if found != prefix or not (token_id.isdecimal() and len(token_id) <= 18) or not secret:
        return None
    return int(token_id), secret


def matches(secret: str, stored: str | None) -> bool:
    """Whether a secret hashes to the stored digest, in the same time when there is none."""
    return hmac.compare_digest(digest(secret), stored or ABSENT) and stored is not None


def bearer(request: Request) -> str:
    """The bearer token in the Authorization header; never read from the URL."""
    scheme, _, token = request.headers.get("Authorization", "").partition(" ")
    return token.strip() if scheme.lower() == "bearer" else ""


def connect_private(path: Path, schema: str) -> sqlite3.Connection:
    """A database only its owner can read, created that way from the start."""
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        os.close(os.open(path, os.O_CREAT | os.O_WRONLY, 0o600))
    db = sqlite3.connect(path)
    db.row_factory = sqlite3.Row
    db.executescript(schema)
    return db
