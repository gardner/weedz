"""Ed25519 signing in a DSSE envelope, and custody rules for the private key.

DSSE (https://github.com/secure-systems-lab/dsse) signs the exact payload bytes together
with their type, so a verifier never re-serialises JSON: it checks the signature over the
bytes it received, then parses them. The private key lives in one owner-only file outside
any git work tree; nothing here prints, logs or returns it.
"""

import base64
import binascii
import hashlib
import os
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

PAYLOAD_TYPE = "application/vnd.weedz.bundle+json; version=1"


class BundleRejected(ValueError):
    """A bundle, or one of its artefacts, that a device must not use."""


class KeyRefused(ValueError):
    """A signing key kept somewhere it could leak."""


def pae(payload_type: str, payload: bytes) -> bytes:
    """DSSE's pre-authentication encoding: what is actually signed."""
    kind = payload_type.encode()
    return b"DSSEv1 %d %b %d %b" % (len(kind), kind, len(payload), payload)


def _raw(key: Ed25519PublicKey) -> bytes:
    return key.public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)


def public_key_text(key: Ed25519PrivateKey | Ed25519PublicKey) -> str:
    """The base64 raw public key, as an app pins it."""
    public = key.public_key() if isinstance(key, Ed25519PrivateKey) else key
    return base64.b64encode(_raw(public)).decode()


def key_id(public_key: str) -> str:
    """A short, stable name for a public key: the start of its raw bytes' SHA-256."""
    return hashlib.sha256(base64.b64decode(public_key)).hexdigest()[:16]


def in_git_work_tree(path: Path) -> bool:
    return any((folder / ".git").exists() for folder in path.resolve().parents)


def generate_key(path: Path) -> str:
    """Write a new owner-only private key to `path` and return only its public key."""
    if in_git_work_tree(path):
        raise KeyRefused(f"{path} is inside a git work tree; keep signing keys outside it")
    if path.exists():
        raise KeyRefused(f"{path} already exists; a key is never overwritten")
    key = Ed25519PrivateKey.generate()
    pem = key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    with os.fdopen(descriptor, "wb") as handle:
        handle.write(pem)
    return public_key_text(key)


def load_private_key(path: Path) -> Ed25519PrivateKey:
    """The signing key, refused if others can read it or it sits in a git work tree."""
    if in_git_work_tree(path):
        raise KeyRefused(f"{path} is inside a git work tree; move it out and rotate it")
    if path.stat().st_mode & 0o077:
        raise KeyRefused(f"{path} is readable by other users; chmod 600 it and rotate it")
    key = serialization.load_pem_private_key(path.read_bytes(), password=None)
    if not isinstance(key, Ed25519PrivateKey):
        raise KeyRefused(f"{path} is not an Ed25519 private key")
    return key


def sign(payload: bytes, key: Ed25519PrivateKey) -> dict[str, Any]:
    """A DSSE envelope carrying `payload` and one signature by `key`."""
    signature = key.sign(pae(PAYLOAD_TYPE, payload))
    return {
        "payloadType": PAYLOAD_TYPE,
        "payload": base64.b64encode(payload).decode(),
        "signatures": [
            {"keyid": key_id(public_key_text(key)), "sig": base64.b64encode(signature).decode()}
        ],
    }


def _signed_by(message: bytes, signature: Mapping[str, Any], trusted: Sequence[str]) -> bool:
    for public in trusted:
        if key_id(public) != signature.get("keyid"):
            continue
        key = Ed25519PublicKey.from_public_bytes(base64.b64decode(public))
        try:
            key.verify(base64.b64decode(signature.get("sig", ""), validate=True), message)
            return True
        except (InvalidSignature, binascii.Error, TypeError, ValueError):
            return False
    return False


def verify(envelope: Mapping[str, Any], trusted: Sequence[str]) -> bytes:
    """The payload bytes, once a pinned key's signature over them checks out."""
    if envelope.get("payloadType") != PAYLOAD_TYPE:
        raise BundleRejected(f"Unexpected payload type; expected {PAYLOAD_TYPE!r}")
    try:
        payload = base64.b64decode(envelope.get("payload", ""), validate=True)
    except (binascii.Error, TypeError) as error:
        raise BundleRejected("The payload is not valid base64") from error
    message = pae(PAYLOAD_TYPE, payload)
    signatures = envelope.get("signatures")
    if not isinstance(signatures, list) or not any(
        isinstance(item, Mapping) and _signed_by(message, item, trusted) for item in signatures
    ):
        raise BundleRejected("No valid signature from a pinned key")
    return payload
