"""Serve only an external, sanitized capture snapshot; every write route is blocked."""

import argparse
import hashlib
import json
import sqlite3
import tempfile
from collections.abc import Iterator
from contextlib import closing, contextmanager
from pathlib import Path

import uvicorn
from demo_paths import outside_git
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response
from starlette.middleware.base import RequestResponseEndpoint

from weedz.discovery.api import create_app


def copy_verified_images(source: Path, target: Path) -> None:
    proof = json.loads((source / "capture-provenance.json").read_text())
    if not isinstance(proof, dict) or not isinstance(proof.get("photos"), list):
        raise ValueError("Snapshot photo manifest is missing or malformed")
    copied: set[str] = set()
    for record in proof["photos"]:
        name = record.get("file") if isinstance(record, dict) else None
        if not isinstance(name, str):
            raise ValueError("Snapshot photo path is missing")
        relative = Path(name)
        if len(relative.parts) != 2 or relative.parts[0] != "images" or ".." in relative.parts:
            raise ValueError("Snapshot photo path must remain inside images")
        key = relative.as_posix()
        if key in copied:
            raise ValueError("Snapshot photo manifest contains duplicate files")
        copied.add(key)
        image = (source / relative).resolve()
        if not image.is_relative_to(source.resolve() / "images"):
            raise ValueError("Snapshot photo path escapes images")
        raw = image.read_bytes()
        if hashlib.sha256(raw).hexdigest() != record.get("sha256"):
            raise ValueError("Snapshot image checksum differs from its source credits")
        (target / relative).parent.mkdir(exist_ok=True)
        (target / relative).write_bytes(raw)


@contextmanager
def snapshot_app(source: Path, instance: str = "") -> Iterator[FastAPI]:
    if any((source / f"discovery.sqlite3{suffix}").exists() for suffix in ("-wal", "-shm")):
        raise ValueError("Serve only a closed standalone snapshot without WAL sidecars")
    with tempfile.TemporaryDirectory(prefix="weedz-snapshot-server-") as temporary:
        copy = Path(temporary)
        with (
            closing(
                sqlite3.connect(
                    (source / "discovery.sqlite3").as_uri() + "?mode=ro&immutable=1", uri=True
                )
            ) as original,
            closing(sqlite3.connect(copy / "discovery.sqlite3")) as target,
        ):
            original.backup(target)
        copy_verified_images(source, copy)
        app = create_app(copy)

        @app.middleware("http")
        async def read_only(request: Request, call_next: RequestResponseEndpoint) -> Response:
            if request.method in {"GET", "HEAD"} and request.url.path == "/runs/capture_identity":
                return JSONResponse({"capture_instance": instance})
            if request.method not in {"GET", "HEAD"}:
                return JSONResponse(
                    {"detail": "The demonstration snapshot is read-only"}, status_code=405
                )
            return await call_next(request)

        yield app


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", type=Path, required=True)
    parser.add_argument("--port", type=int, default=8312)
    parser.add_argument("--instance", default="")
    args = parser.parse_args()
    root = outside_git(args.snapshot)
    if not (root / "capture-provenance.json").is_file():
        raise ValueError("Serve only a sanitized copy made by capture_demo_snapshot.py")
    with snapshot_app(root, args.instance) as app:
        uvicorn.run(app, host="127.0.0.1", port=args.port)


if __name__ == "__main__":
    main()
