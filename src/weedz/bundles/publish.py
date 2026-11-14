"""Publish a bundle as a static tree any host or CDN can serve.

    <out>/manifest.json                 the signed DSSE envelope (re-fetched; never cached)
    <out>/artifacts/sha256/<hex>         each artefact under its own hash (immutable)

Nothing is written until the parity gate passes and the sequence is newer than the one
already published, and every file is written atomically, so a reader never sees a
manifest that lists an artefact not yet in place.
"""

import base64
import json
import logging
import os
import shutil
import tempfile
from pathlib import Path

from weedz.bundles.canonical import canonical
from weedz.bundles.manifest import BundleRejected, BundleSpec, build_manifest, check_artefact
from weedz.bundles.signing import key_id, load_private_key, public_key_text, sign

logger = logging.getLogger(__name__)
MANIFEST = "manifest.json"


def artefact_path(out: Path, sha256: str) -> Path:
    return out / "artifacts" / "sha256" / sha256


def published_sequence(out: Path) -> int:
    """The sequence of the manifest already in `out`, or 0 when there is none."""
    path = out / MANIFEST
    if not path.exists():
        return 0
    envelope = json.loads(path.read_text())
    return int(json.loads(base64.b64decode(envelope["payload"]))["sequence"])


def _atomic_copy(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary = tempfile.mkstemp(dir=target.parent, prefix=".partial-")
    os.close(handle)
    try:
        shutil.copyfile(source, temporary)
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


def publish(spec: BundleSpec, key_path: Path, out: Path) -> str:
    """Sign and publish `spec` into `out`; returns the public key that verifies it."""
    key = load_private_key(key_path)
    manifest = build_manifest(spec)
    previous = published_sequence(out)
    if manifest["sequence"] <= previous:
        raise BundleRejected(
            f"sequence {manifest['sequence']} must be greater than the published {previous}"
        )
    sources = {"image_model": spec.image_model.path, "text_table": spec.text_table}
    for part, source in sources.items():
        entry = manifest[part]
        target = artefact_path(out, entry["sha256"])
        if not target.exists():
            _atomic_copy(Path(source), target)
        check_artefact(target, entry)
    _atomic_write(out / MANIFEST, json.dumps(sign(canonical(manifest), key), indent=2).encode())
    public = public_key_text(key)
    logger.info("Published bundle %d signed by key %s", manifest["sequence"], key_id(public))
    return public
