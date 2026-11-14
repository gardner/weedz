"""A follow-up package's files: JSON, Markdown and the photos their licences let us share."""

import hashlib
import io
import json
import zipfile
from pathlib import Path
from typing import Any

from weedz.discovery.activities import export
from weedz.discovery.leads import selections
from weedz.discovery.package import follow_up_package
from weedz.discovery.package_report import to_markdown
from weedz.discovery.store import Store


def _retained(root: Path, photo: dict[str, Any]) -> bytes:
    """The run's own copy of a photo, only while it still matches its recorded checksum."""
    path = (root / photo["image_path"]).resolve()
    if not photo["image_path"] or not path.is_relative_to(root / "images") or not path.is_file():
        raise ValueError(f"No retained image for {photo['id']}")
    content = path.read_bytes()
    if hashlib.sha256(content).hexdigest() != photo["sha256"]:
        raise ValueError(f"Image checksum mismatch for {photo['id']}; not packaged")
    return content


def package_contents(
    store: Store, run_id: str, generated_at: str
) -> tuple[dict[str, Any], dict[str, bytes]]:
    """The package, and its files by path: package.json, package.md and permitted photos."""
    result = export(store, run_id)
    package = follow_up_package(result, selections(store, run_id), generated_at)
    photos = {photo["id"]: photo for photo in result["photos"]}
    files = {
        "package.json": (json.dumps(package, indent=2, ensure_ascii=False) + "\n").encode(),
        "package.md": to_markdown(package).encode(),
    }
    for lead in package["leads"]:
        if lead["image"]["included"]:
            files[lead["image"]["file"]] = _retained(store.root, photos[lead["photo_id"]])
    return package, files


def archive(files: dict[str, bytes]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as bundle:
        for name, content in files.items():
            bundle.writestr(name, content)
    return buffer.getvalue()


def write(files: dict[str, bytes], destination: Path) -> None:
    for name, content in files.items():
        path = destination / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
