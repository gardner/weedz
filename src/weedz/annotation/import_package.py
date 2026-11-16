"""Closed annotation-package snapshots, verified before any human record is trusted."""

import hashlib
import io
import json
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from urllib.parse import parse_qs, urlsplit

from PIL import Image

from weedz.contract import Sample
from weedz.rights_profiles import RightsProfile, rights_profile_fields

MAX_BYTES = 256 * 1024 * 1024
MAX_MANIFEST_BYTES = 4 * 1024 * 1024
MAX_PACKAGE_BYTES = 512 * 1024 * 1024
MAX_FILES = 10_000
MAX_STRUCTURE_BYTES = 64 * 1024 * 1024
STRUCTURAL_FILES = frozenset({"tasks.json", "private/provenance.json"})


def pinned_bytes(path: Path, expected: str, maximum: int = MAX_BYTES) -> bytes:
    if not path.is_file() or path.is_symlink() or path.stat().st_size > maximum:
        raise ValueError("Missing, symlinked or oversized import input")
    with path.open("rb") as stream:
        raw = stream.read(maximum + 1)
    if len(raw) > maximum or hashlib.sha256(raw).hexdigest() != expected:
        raise ValueError("Import input checksum mismatch or resource cap exceeded")
    return raw


def relative_file(root: Path, name: str) -> Path:
    relative = PurePosixPath(name)
    if (
        relative.is_absolute()
        or "\\" in name
        or ":" in name
        or any(part in ("", ".", "..") for part in name.split("/"))
    ):
        raise ValueError("Package file must use a safe relative path")
    path = root / name
    if not path.resolve().is_relative_to(root.resolve()):
        raise ValueError("Package asset escapes its root")
    return path


@dataclass(frozen=True)
class Package:
    sha256: str
    files: dict[str, bytes]
    samples: dict[str, Sample]
    tasks: dict[str, dict]
    rights_profile: RightsProfile | None = None
    human_import: bool = False
    task_bindings: dict[str, int] | None = None
    export_sha256: str | None = None
    owned_export_sha256: list[str] | None = None


def _geometry(media: bytes, sample: Sample) -> None:
    with Image.open(io.BytesIO(media)) as image:
        if (
            image.size != (sample.media.width, sample.media.height)
            or image.width * image.height > 40_000_000
            or image.format != "PNG"
            or image.mode != "RGB"
        ):
            raise ValueError("Canonical image geometry/format mismatch")
        image.load()
        if image.info or image.getexif():
            raise ValueError("Canonical image must be metadata-free upright RGB")


def read_package(root: Path, expected: str) -> Package:
    raw = pinned_bytes(root / "manifest.json", expected, MAX_MANIFEST_BYTES)
    manifest = json.loads(raw)
    if not isinstance(manifest.get("files"), dict):
        raise ValueError("Annotation package needs a closed file manifest")
    files = _files(root, manifest["files"])
    provenance = json.loads(files["private/provenance.json"])
    records = provenance.get("samples", provenance.get("photos"))
    if not isinstance(records, list) or not 1 <= len(records) <= 1000:
        raise ValueError("Package has no canonical sample provenance")
    samples = {}
    for record in records:
        sample = Sample.model_validate(record["sample"])
        key = hashlib.sha256(f"{sample.id}:{sample.media.sha256}".encode()).hexdigest()
        if key != record["external_id"] or key in samples:
            raise ValueError("Invalid or duplicate canonical task identity")
        media = files.get(sample.media.uri)
        if media is None or hashlib.sha256(media).hexdigest() != sample.media.sha256:
            raise ValueError("Package sample media does not match its pinned image")
        _geometry(media, sample)
        samples[key] = sample
    declared = manifest.get("contract_schema_version")
    if declared is not None and declared != max(s.schema_version for s in samples.values()):
        raise ValueError("Package contract schema version differs from its actual samples")
    profile = manifest.get("rights_profile")
    if profile is not None:
        rights_profile_fields(profile)
    imported = {"project_namespace", "project_id", "source_package_sha256"} <= manifest.keys()
    return Package(
        expected,
        files,
        samples,
        _tasks(files, samples),
        profile,
        imported,
        manifest.get("task_bindings") if imported else None,
        manifest.get("export_sha256") if imported else None,
        manifest.get("owned_export_sha256") if imported else None,
    )


def _tasks(files: dict[str, bytes], samples: dict[str, Sample]) -> dict[str, dict]:
    tasks = {}
    for task in json.loads(files["tasks.json"]):
        key = task["meta"]["external_id"]
        if key not in samples or key in tasks:
            raise ValueError("Task set differs from canonical sample identities")
        _task_image(task, samples[key])
        tasks[key] = task
    if tasks.keys() != samples.keys():
        raise ValueError("Package is missing canonical tasks")
    return tasks


def _task_image(task: dict, sample: Sample) -> None:
    url = urlsplit(task["data"]["image"])
    expected = sample.media.uri.removeprefix("images/")
    if url.path != "/data/local-files/" or url.fragment or parse_qs(url.query) != {"d": [expected]}:
        raise ValueError("Task image does not identify its canonical media")


def _files(root: Path, references: dict[str, str]) -> dict[str, bytes]:
    if len(references) > MAX_FILES:
        raise ValueError("Package file count exceeds resource cap")
    files: dict[str, bytes] = {}
    total = 0
    for name, checksum in references.items():
        raw = pinned_bytes(
            relative_file(root, name), checksum, min(_file_limit(name), MAX_PACKAGE_BYTES - total)
        )
        files[name] = raw
        total += len(raw)
    return files


def check_output_files(files: dict[str, bytes]) -> None:
    """Published packages must fit the same bounds as subsequent replay."""
    if (
        len(files) > MAX_FILES
        or sum(map(len, files.values())) > MAX_PACKAGE_BYTES
        or any(len(raw) > _file_limit(name) for name, raw in files.items())
    ):
        raise ValueError("Import output exceeds replay resource cap")


def _file_limit(name: str) -> int:
    return min(MAX_BYTES, MAX_STRUCTURE_BYTES) if name in STRUCTURAL_FILES else MAX_BYTES


def check_output_manifest(encoded: bytes) -> None:
    if len(encoded) > MAX_MANIFEST_BYTES:
        raise ValueError("Generated manifest exceeds the replay manifest resource cap")
