"""Publish a bundle as a static tree any host or CDN can serve.

    <out>/manifest.json                 the signed DSSE envelope (re-fetched; never cached)
    <out>/artifacts/sha256/<hex>         each artefact under its own hash (immutable)

Nothing is written until the parity gate passes and the sequence is newer than the one
already published, and every file is written atomically, so a reader never sees a
manifest that lists an artefact not yet in place.
"""

import base64
import fcntl
import json
import logging
import os
import shutil
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager, suppress
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from weedz.bundles.canonical import canonical
from weedz.bundles.manifest import BundleRejected, BundleSpec, build_manifest, check_artefact
from weedz.bundles.signing import key_id, load_private_key, public_key_text, sign

logger = logging.getLogger(__name__)
MANIFEST = "manifest.json"
LOCK = ".publish.lock"


def artefact_path(out: Path, sha256: str) -> Path:
    return out / "artifacts" / "sha256" / sha256


def published_sequence(out: Path) -> int:
    """The sequence of the manifest already in `out`, or 0 when there is none."""
    path = out / MANIFEST
    if not path.exists():
        return 0
    envelope = json.loads(path.read_text())
    return int(json.loads(base64.b64decode(envelope["payload"]))["sequence"])


def _place_artefact(source: Path, target: Path, entry: dict) -> None:
    """Put exactly the listed bytes at `target`: a copy is checked before it replaces
    anything, and a file already there that fails the check (say, a truncated earlier
    copy) is replaced rather than trusted."""
    with suppress(BundleRejected, FileNotFoundError):
        check_artefact(target, entry)
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary = tempfile.mkstemp(dir=target.parent, prefix=".partial-")
    os.close(handle)
    try:
        shutil.copyfile(source, temporary)
        check_artefact(Path(temporary), entry)
        os.chmod(temporary, 0o644)
        os.replace(temporary, target)
    finally:
        Path(temporary).unlink(missing_ok=True)


def _atomic_write(target: Path, data: bytes) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary = tempfile.mkstemp(dir=target.parent, prefix=".partial-")
    try:
        with os.fdopen(handle, "wb") as stream:
            stream.write(data)
        os.chmod(temporary, 0o644)
        os.replace(temporary, target)
    finally:
        Path(temporary).unlink(missing_ok=True)


@contextmanager
def lock(out: Path) -> Iterator[None]:
    """Hold the tree's publish lock, so two publishers cannot both pass the sequence check
    and have the older manifest written last."""
    out.mkdir(parents=True, exist_ok=True)
    with (out / LOCK).open("a") as handle:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise BundleRejected(f"Another publish to {out} is in progress") from error
        try:
            yield
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)


def _place(spec: BundleSpec, manifest: dict, key: Ed25519PrivateKey, out: Path) -> None:
    previous = published_sequence(out)
    if manifest["sequence"] <= previous:
        raise BundleRejected(
            f"sequence {manifest['sequence']} must be greater than the published {previous}"
        )
    sources = {"image_model": spec.image_model.path, "text_table": spec.text_table}
    for part, source in sources.items():
        entry = manifest[part]
        _place_artefact(Path(source), artefact_path(out, entry["sha256"]), entry)
    _atomic_write(out / MANIFEST, json.dumps(sign(canonical(manifest), key), indent=2).encode())


def publish(spec: BundleSpec, key_path: Path, out: Path) -> str:
    """Sign and publish `spec` into `out`; returns the public key that verifies it."""
    key = load_private_key(key_path)
    manifest = build_manifest(spec)
    with lock(out):
        _place(spec, manifest, key, out)
    public = public_key_text(key)
    logger.info("Published bundle %d signed by key %s", manifest["sequence"], key_id(public))
    return public
