"""A follow-up package's files: JSON, Markdown and the photos their licences let us share."""

import hashlib
import io
import json
import zipfile
from pathlib import Path
from typing import Any

from weedz.discovery.activities import export
from weedz.discovery.package import follow_up_package, link_only
from weedz.discovery.package_report import to_markdown
from weedz.discovery.store import Store

MISSING = "Not included: no retained copy of this photo; follow the source link to view it"
CHANGED = (
    "Not included: the retained copy no longer matches its recorded checksum; follow the "
    "source link to view it"
)


def _retained(root: Path, photo: dict[str, Any]) -> bytes | str:
    """The run's own copy of a photo while it still matches its recorded checksum, or why
    it cannot be packaged."""
    path = (root / photo["image_path"]).resolve()
    if not photo["image_path"] or not path.is_relative_to(root / "images") or not path.is_file():
        return MISSING
    content = path.read_bytes()
    return content if hashlib.sha256(content).hexdigest() == photo["sha256"] else CHANGED


def package_contents(
    store: Store, run_id: str, generated_at: str
) -> tuple[dict[str, Any], dict[str, bytes]]:
    """The package, and its files by path: package.json, package.md and permitted photos.
    A permitted photo whose retained copy is missing or changed is linked instead."""
    result = export(store, run_id)
    package = follow_up_package(result, result["lead_selections"], generated_at)
    photos = {photo["id"]: photo for photo in result["photos"]}
    files: dict[str, bytes] = {}
    for lead in package["leads"]:
        if not lead["image"]["included"]:
            continue
        content = _retained(store.root, photos[lead["photo_id"]])
        if isinstance(content, str):
            lead["image"] = link_only(lead["image"], content)
        else:
            files[lead["image"]["file"]] = content
    return package, {
        "package.json": (json.dumps(package, indent=2, ensure_ascii=False) + "\n").encode(),
        "package.md": to_markdown(package).encode(),
    } | files


def archive(files: dict[str, bytes]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as bundle:
        for name, content in files.items():
            bundle.writestr(name, content)
    return buffer.getvalue()


def write(files: dict[str, bytes], destination: Path) -> None:
    """Write each file under `destination`, refusing any path that would leave it."""
    inside = destination.resolve()
    paths = {name: (inside / name).resolve() for name in files}
    if any(not path.is_relative_to(inside) for path in paths.values()):
        raise ValueError(f"A package file would be written outside {destination}")
    for name, content in files.items():
        path = paths[name]
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
