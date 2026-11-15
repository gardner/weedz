"""Build immutable annotation packages without exposing interrupted staging directories."""

import fcntl
import hashlib
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
    for reference in inputs.values():
        read_artifact(root, reference, 128_000_000)
    with (folder / ".package.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if not destination.exists():
            staging = Path(tempfile.mkdtemp(prefix="package-pending-", dir=folder))
            staging.rmdir()  # The exporter requires a new, exclusively created destination.
            try:
                export_samples(
                    batch.manifest,
                    staging,
                    proposals=root / inputs["proposals"]["path"],
                    frame_results=root / inputs["frame"]["path"] if "frame" in inputs else None,
                    regional_results=root / inputs["regions"]["path"]
                    if "regions" in inputs
                    else None,
                    tiled_results=root / inputs["tiles"]["path"] if "tiles" in inputs else None,
                )
                _sync_package(staging)
                os.rename(staging, destination)
                sync_directory(folder)
            finally:
                if staging.exists():
                    shutil.rmtree(staging)
        _sync_package(destination)
        manifest = destination / "manifest.json"
        sha = hashlib.sha256(read_owned_file(manifest, root, 1024 * 1024)).hexdigest()
        validate_package(destination, sha)
        return {"path": str(manifest.relative_to(root)), "sha256": sha}
