"""Build immutable annotation packages without exposing interrupted staging directories."""

import fcntl
import hashlib
import json
import os
import shutil
import tempfile
from pathlib import Path

from weedz.annotation.samples import export_samples
from weedz.batches.package import validate_package
from weedz.batches.storage import ClosedBatch, read_artifact, read_owned_file
from weedz.segmentation.artifacts import durable_mkdir, sync_directory


def _sync_package(root: Path) -> None:
    for path in root.rglob("*"):
        if path.is_file():
            with path.open("rb") as stream:
                os.fsync(stream.fileno())
    directories = [path for path in root.rglob("*") if path.is_dir()]
    for directory in sorted(directories, key=lambda path: len(path.parts), reverse=True):
        sync_directory(directory)
    sync_directory(root)


def build_package(
    root: Path, batch: ClosedBatch, namespace: str, inputs: dict[str, dict]
) -> dict[str, str]:
    folder = root / namespace
    durable_mkdir(folder)
    destination = folder / "package"
    verified = {name: read_artifact(root, ref, 128_000_000) for name, ref in inputs.items()}
    source = {"path": str(batch.manifest.relative_to(root)), "sha256": batch.sha256}
    read_artifact(root, source, 32 * 1024 * 1024)
    with (folder / ".package.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if not destination.exists():
            staging = Path(tempfile.mkdtemp(prefix="package-pending-", dir=folder))
            staging.rmdir()  # The exporter requires a new, exclusively created destination.
            try:
                with tempfile.TemporaryDirectory(prefix="verified-inputs-", dir=folder) as private:
                    snapshots = {}
                    for name, encoded in verified.items():
                        path = Path(private) / f"{name}.json"
                        path.write_bytes(encoded)
                        snapshots[name] = path
                    export_samples(
                        batch.manifest,
                        staging,
                        proposals=snapshots["proposals"],
                        frame_results=snapshots["frame"] if "frame" in inputs else None,
                        regional_results=snapshots["regions"] if "regions" in inputs else None,
                        tiled_results=snapshots["tiles"] if "tiles" in inputs else None,
                        rights_profile=batch.rights_profile,
                    )
                for reference in inputs.values():
                    read_artifact(root, reference, 128_000_000)
                read_artifact(root, source, 32 * 1024 * 1024)
                _source_identity(staging, batch)
                _sync_package(staging)
                os.rename(staging, destination)
                sync_directory(folder)
            finally:
                if staging.exists():
                    shutil.rmtree(staging)
        _source_identity(destination, batch)
        _sync_package(destination)
        manifest = destination / "manifest.json"
        sha = hashlib.sha256(read_owned_file(manifest, root, 1024 * 1024)).hexdigest()
        validate_package(destination, sha, rights_profile=batch.rights_profile)
        return {"path": str(manifest.relative_to(root)), "sha256": sha}


def _source_identity(package: Path, batch: ClosedBatch) -> None:
    document = json.loads((package / "private/provenance.json").read_text(encoding="utf-8"))
    if document.get("rights_profile", "public-cc0-by") != batch.rights_profile:
        raise ValueError("Package source rights profile changed during export")
    if document["source_manifest_sha256"] != batch.sha256:
        raise ValueError("Package source manifest checksum mismatch")
    records = document["samples"]
    if len(records) != len(batch.samples):
        raise ValueError("Package source sample coverage mismatch")
    for record, original in zip(records, batch.samples, strict=True):
        expected = original.model_dump(mode="json")
        expected["geography"] = None
        expected["media"]["uri"] = f"images/corpus/{original.media.sha256}.png"
        if record["sample"] != expected:
            raise ValueError("Package source sample identity or rights changed during export")
