"""A follow-up package's files: JSON, Markdown and the photos their licences let us share.

Photos are named by their path on disk and copied or streamed from there, never held in
memory together, so a package of many large photos stays cheap to build.
"""

import hashlib
import json
import shutil
import zipfile
from pathlib import Path
from typing import IO, Any

from weedz.discovery.activities import export
from weedz.discovery.package import follow_up_package, link_only
from weedz.discovery.package_report import to_markdown
from weedz.discovery.store import Store

MISSING = "Not included: no retained copy of this photo; follow the source link to view it"
CHANGED = (
    "Not included: the retained copy no longer matches its recorded checksum; follow the "
    "source link to view it"
)


def _retained(root: Path, photo: dict[str, Any]) -> Path | str:
    """The run's own copy of a photo while it still matches its recorded checksum, or why
    it cannot be packaged."""
    path = (root / photo["image_path"]).resolve()
    if not photo["image_path"] or not path.is_relative_to(root / "images") or not path.is_file():
        return MISSING
    with path.open("rb") as handle:
        digest = hashlib.file_digest(handle, "sha256").hexdigest()
    return path if digest == photo["sha256"] else CHANGED


def package_contents(
    store: Store, run_id: str, generated_at: str
) -> tuple[dict[str, Any], dict[str, Path]]:
    """The package, and the retained copy of each permitted photo by its package path. A
    permitted photo whose retained copy is missing or changed is linked instead."""
    result = export(store, run_id)
    package = follow_up_package(result, result["lead_selections"], generated_at)
    photos = {photo["id"]: photo for photo in result["photos"]}
    files: dict[str, Path] = {}
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


def archive(package: dict[str, Any], photos: dict[str, Path], target: IO[bytes]) -> None:
    """Write the package as a zip to `target`, streaming each photo from disk."""
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as bundle:
        for name, content in texts(package).items():
            bundle.writestr(name, content)
        for name, path in photos.items():
            bundle.write(path, name)


def write(package: dict[str, Any], photos: dict[str, Path], destination: Path) -> None:
    """Write the package under `destination`, refusing any path that would leave it."""
    inside = destination.resolve()
    targets = {name: (inside / name).resolve() for name in photos}
    if any(not target.is_relative_to(inside) for target in targets.values()):
        raise ValueError(f"A package file would be written outside {destination}")
    inside.mkdir(parents=True, exist_ok=True)
    for name, content in texts(package).items():
        (inside / name).write_bytes(content)
    for name, path in photos.items():
        targets[name].parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, targets[name])
