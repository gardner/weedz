"""Export a frozen NZ pilot package as a reviewer-only portable ZIP."""

import argparse
import hashlib
import json
import os
import re
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Literal
from zipfile import ZIP_STORED, ZipFile, ZipInfo

from weedz.annotation.pilot_effort import Row

Arm = Literal["blind", "assisted"]
IMAGE_URL = "/data/local-files/?d="
PREFIX = re.compile(r"[a-zA-Z0-9_-]{1,100}")
SHA256 = re.compile(r"[0-9a-f]{64}")
BASE_FIELDS = {"image", "photo_credit", "source_dataset"}
REVIEWER_GUIDE = """# Weedz NZ reviewer pilot

1. Use `label-config.xml` as the Label Studio project labeling configuration.
2. Configure the extracted `images/` folder as the local files document root.
   Register its arm subfolder as local storage for the project, then import
   `tasks.json`. Keep the existing relative paths and task data.
3. Inspect the whole photo. Mark visible watchlist plants only when there is
   enough evidence to identify them. Use the unsure option when needed.
4. Keep the credit with each image. Open the linked source observation only
   after submitting the task, so its subject identification cannot influence
   your initial answer.
5. Export full Label Studio JSON with task data, task metadata and annotations.
   Record interface problems and interruptions separately.

The operator uses the original private package for export verification.
The distribution manifest records hashes for the reviewer files.
"""


def _digest(blob: bytes) -> str:
    return hashlib.sha256(blob).hexdigest()


def _bound_bytes(package: Path, path: str, pinned: dict[str, str]) -> bytes:
    file = (package / path).resolve()
    if not file.is_relative_to(package):
        raise ValueError("Reviewer file escapes its package")
    data = file.read_bytes()
    if _digest(data) != pinned.get(path):
        raise ValueError(
            f"Reviewer file is absent from the manifest or its checksum differs: {path}"
        )
    return data


def _image_path(url: str, image_sha: str, *, search: bool = False) -> str:
    if not isinstance(url, str) or not url.startswith(IMAGE_URL):
        raise ValueError("Expected a package-local image URL")
    prefix, slash, name = url.removeprefix(IMAGE_URL).partition("/")
    expected = image_sha + ("-search.png" if search else ".png")
    if not slash or not PREFIX.fullmatch(prefix) or name != expected:
        raise ValueError("Task image URL must match the package image hash and storage prefix")
    return f"images/{prefix}/{name}"


def _paths(task: Row, arm: Arm) -> list[str]:
    if set(task) != {"data", "meta"}:
        raise ValueError("Reviewer task cannot include annotations, predictions or private fields")
    data, meta = task["data"], task["meta"]
    allowed = BASE_FIELDS | ({"review_hint", "search_preview"} if arm == "assisted" else set())
    if set(data) != allowed or set(meta) != {"external_id", "image_sha256"}:
        raise ValueError("Task data and metadata do not match the review arm")
    image_sha = meta["image_sha256"]
    if not isinstance(image_sha, str) or not SHA256.fullmatch(image_sha):
        raise ValueError("Expected a canonical source image checksum")
    original = _image_path(data["image"], image_sha)
    if arm == "blind":
        return [original]
    preview = _image_path(data["search_preview"], image_sha, search=True)
    if Path(preview).parent != Path(original).parent:
        raise ValueError("Search preview and original must share the arm storage prefix")
    return [original, preview]


def _member(archive: ZipFile, name: str, data: bytes) -> None:
    info = ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
    info.external_attr = 0o600 << 16
    info.compress_type = ZIP_STORED
    archive.writestr(info, data)


def build(package: Path, output: Path, *, arm: Arm) -> Row:
    """Write only reviewer material and preserve every original task payload."""
    if arm not in {"blind", "assisted"}:
        raise ValueError("Unknown review arm")
    package = package.resolve()
    source_manifest = (package / "manifest.json").read_bytes()
    manifest = json.loads(source_manifest)
    pinned = manifest["files"]
    tasks_raw = _bound_bytes(package, "tasks.json", pinned)
    tasks = json.loads(tasks_raw)
    if not tasks or len(tasks) != manifest["task_count"]:
        raise ValueError("Task count differs from the frozen package")
    image_paths = {path for task in tasks for path in _paths(task, arm)}
    paths = sorted({"label-config.xml", "tasks.json"} | image_paths)
    result: Row = {
        "schema": 1,
        "arm": arm,
        "task_count": len(tasks),
        "operator_package_manifest_sha256": _digest(source_manifest),
        "files": {},
    }
    output = output.resolve()
    if output.is_relative_to(package):
        raise ValueError("Use a separate output location for the reviewer archive")
    with NamedTemporaryFile(dir=output.parent) as temporary:
        with ZipFile(temporary, "w") as archive:
            for path in paths:
                data = _bound_bytes(package, path, pinned)
                digest = _digest(data)
                original = path in image_paths and not path.endswith("-search.png")
                if original and Path(path).stem != digest:
                    raise ValueError("Original image bytes differ from the task checksum")
                _member(archive, path, data)
                result["files"][path] = digest
            guide = REVIEWER_GUIDE.encode("utf-8")
            _member(archive, "README.md", guide)
            result["files"]["README.md"] = _digest(guide)
            _member(archive, "distribution-manifest.json", json.dumps(result, indent=2).encode())
        temporary.flush()
        os.fsync(temporary.fileno())
        os.link(temporary.name, output)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--arm", choices=("blind", "assisted"), required=True)
    args = parser.parse_args()
    result = build(args.package, args.output, arm=args.arm)
    print(f"Built {result['arm']} reviewer bundle for {result['task_count']} tasks.")


if __name__ == "__main__":
    main()
