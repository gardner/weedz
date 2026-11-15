"""Serve only an external, sanitized capture snapshot; every write route is blocked."""

import argparse
import shutil
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
        if (source / "images").exists():
            shutil.copytree(source / "images", copy / "images")
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
