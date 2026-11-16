"""Publish one new closed local import package from already verified snapshots."""

import hashlib
import json
import os
import tempfile
from pathlib import Path

from weedz.annotation.export import _output
from weedz.annotation.import_package import check_output_files, relative_file


def json_bytes(value: object) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False, indent=2) + "\n"
    ).encode("utf-8")


def write_import(source: Path, output: Path, files: dict[str, bytes], details: dict) -> dict:
    check_output_files(files)
    output = _output(source.resolve(), output)
    output.parent.mkdir(parents=True, exist_ok=True)
    receipt = {
        **details,
        "files": {name: hashlib.sha256(raw).hexdigest() for name, raw in sorted(files.items())},
    }
    with tempfile.TemporaryDirectory(prefix=".human-import-", dir=output.parent) as temporary:
        staging = Path(temporary) / "package"
        staging.mkdir(mode=0o700)
        for name, raw in {**files, "manifest.json": json_bytes(receipt)}.items():
            path = relative_file(staging, name)
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("xb") as stream:
                stream.write(raw)
                stream.flush()
                os.fsync(stream.fileno())
        (staging / "private").chmod(0o700)
        for directory in sorted((p for p in staging.rglob("*") if p.is_dir()), reverse=True):
            _sync(directory)
        _sync(staging)
        if output.exists() or output.is_symlink():
            raise ValueError("Import output already exists")
        staging.rename(output)
        _sync(output.parent)
    return receipt


def _sync(directory: Path) -> None:
    descriptor = os.open(directory, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
