"""A follow-up package's files: JSON, Markdown and the photos their licences let us share.

Photos are named by their path on disk and copied or streamed from there, never held in
memory together, so a package of many large photos stays cheap to build.
"""

import hashlib
import json
import shutil
import tempfile
import zipfile
from pathlib import Path
from typing import IO, Any, NamedTuple

from weedz.discovery.activities import export
from weedz.discovery.package import follow_up_package, link_only
from weedz.discovery.package_report import to_markdown
from weedz.discovery.store import Store

MISSING = "Not included: no retained copy of this photo; follow the source link to view it"
CHANGED = (
    "Not included: the retained copy no longer matches its recorded checksum; follow the "
    "source link to view it"
)


class Retained(NamedTuple):
    """A run's retained copy of a photo and the SHA-256 it must still have when copied."""

    path: Path
    sha256: str


def _copy_verified(photo: Retained, target: IO[bytes]) -> None:
    """Stream the photo into `target`, failing if its bytes changed since they were checked,
    so a package never carries bytes other than those its JSON records."""
    digest = hashlib.sha256()
    with photo.path.open("rb") as source:
        while chunk := source.read(1 << 16):
            digest.update(chunk)
            target.write(chunk)
    if digest.hexdigest() != photo.sha256:
        raise ValueError(f"{photo.path.name} changed after it was checked; package again")


def _retained(root: Path, photo: dict[str, Any]) -> Retained | str:
    """The run's own copy of a photo while it still matches its recorded checksum, or why
    it cannot be packaged."""
    path = (root / photo["image_path"]).resolve()
    if not photo["image_path"] or not path.is_relative_to(root / "images") or not path.is_file():
        return MISSING
    with path.open("rb") as handle:
        digest = hashlib.file_digest(handle, "sha256").hexdigest()
    return Retained(path, digest) if digest == photo["sha256"] else CHANGED


def package_contents(
    store: Store, run_id: str, generated_at: str
) -> tuple[dict[str, Any], dict[str, Retained]]:
    """The package, and the retained copy of each permitted photo by its package path. A
    permitted photo whose retained copy is missing or changed is linked instead."""
    result = export(store, run_id)
    package = follow_up_package(result, result["lead_selections"], generated_at)
    photos = {photo["id"]: photo for photo in result["photos"]}
    files: dict[str, Retained] = {}
    for lead in package["leads"]:
        if not lead["image"]["included"]:
            continue
        retained = _retained(store.root, photos[lead["photo_id"]])
        if isinstance(retained, str):
            lead["image"] = link_only(lead["image"], retained)
        else:
            files[lead["image"]["file"]] = retained
    return package, files


def texts(package: dict[str, Any]) -> dict[str, bytes]:
    return {
        "package.json": (json.dumps(package, indent=2, ensure_ascii=False) + "\n").encode(),
        "package.md": to_markdown(package).encode(),
    }


def archive(package: dict[str, Any], photos: dict[str, Retained], target: IO[bytes]) -> None:
    """Write the package as a zip to `target`, streaming and re-verifying each photo."""
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as bundle:
        for name, content in texts(package).items():
            bundle.writestr(name, content)
        for name, photo in photos.items():
            with bundle.open(name, "w") as entry:
                _copy_verified(photo, entry)


def _fill(folder: Path, package: dict[str, Any], photos: dict[str, Retained]) -> None:
    """Copy and verify every photo, then write the texts that describe them."""
    for name, photo in photos.items():
        target = folder / name
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("wb") as handle:
            _copy_verified(photo, handle)
    for name, content in texts(package).items():
        (folder / name).write_bytes(content)


def write(package: dict[str, Any], photos: dict[str, Retained], destination: Path) -> None:
    """Write the package to `destination`, a new or empty folder, all or nothing: it is
    built in a sibling folder and moved into place only once every photo verifies, so a
    failure never leaves a package whose JSON promises a photo it lacks."""
    inside = destination.resolve()
    if any(not (inside / name).resolve().is_relative_to(inside) for name in photos):
        raise ValueError(f"A package file would be written outside {destination}")
    inside.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=f".{inside.name}-", dir=inside.parent))
    try:
        _fill(staging, package, photos)
        if inside.exists():
            inside.rmdir()  # only an empty folder; anything in it is refused here
        staging.rename(inside)
    except BaseException:
        shutil.rmtree(staging, ignore_errors=True)
        raise
