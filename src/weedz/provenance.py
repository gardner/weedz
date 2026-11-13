"""Pin upstream data and verify the exact inputs used by every experiment."""

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import TypedDict, cast

from weedz.dataset import ATTRIBUTION, LICENSE, REPOSITORY, REVISION, read_observations, safe_path


class DatasetManifest(TypedDict):
    repository: str
    revision: str
    configuration: str
    license: str
    attribution: str
    recorded_at: str
    files: dict[str, str]


def checksum(path: Path) -> str:
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def _files(root: Path) -> list[Path]:
    paths = [row.image_path for row in read_observations(root)]
    paths.extend(root / "data" / "crop" / split / "metadata.csv" for split in ("train", "test"))
    if (root / "README.md").exists():
        paths.append(root / "README.md")
    return sorted(paths)


def record_dataset(root: Path) -> DatasetManifest:
    root = root.resolve()
    manifest: DatasetManifest = {
        "repository": REPOSITORY,
        "revision": REVISION,
        "configuration": "crop",
        "license": LICENSE,
        "attribution": ATTRIBUTION,
        "recorded_at": datetime.now(UTC).isoformat(),
        "files": {str(path.relative_to(root)): checksum(path) for path in _files(root)},
    }
    temporary = root / "manifest.json.tmp"
    temporary.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    temporary.replace(root / "manifest.json")
    return manifest


def verify_dataset(root: Path) -> DatasetManifest:
    manifest_path = root / "manifest.json"
    if not manifest_path.is_file():
        raise ValueError("Dataset has no manifest; run 'uv run main.py fetch' first")
    manifest = cast(DatasetManifest, json.loads(manifest_path.read_text(encoding="utf-8")))
    if (manifest["repository"], manifest["revision"], manifest["configuration"]) != (
        REPOSITORY,
        REVISION,
        "crop",
    ):
        raise ValueError("Dataset manifest does not match the pinned source; fetch it again")
    for relative, expected in manifest["files"].items():
        path = safe_path(root, relative)
        if not path.is_file() or checksum(path) != expected:
            raise ValueError(f"Dataset checksum mismatch: {relative}; fetch it again")
    actual = {str(path.relative_to(root.resolve())) for path in _files(root.resolve())}
    if actual != set(manifest["files"]):
        raise ValueError("Dataset file set differs from its checksum manifest")
    return manifest


def fetch_dataset(root: Path) -> DatasetManifest:
    if (root / "manifest.json").exists():
        return verify_dataset(root)
    from huggingface_hub import snapshot_download

    snapshot_download(
        repo_id=REPOSITORY,
        repo_type="dataset",
        revision=REVISION,
        local_dir=root,
        allow_patterns=["README.md", "data/crop/*/metadata.csv", "data/crop/*/*/*.tif"],
        max_workers=8,
    )
    rows = read_observations(root)
    if sum(row.source_split == "train" for row in rows) != 800 or len(rows) != 900:
        raise ValueError("Pinned dataset should contain 800 training and 100 test observations")
    return record_dataset(root)
