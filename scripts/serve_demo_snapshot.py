"""Serve only an external, sanitized capture snapshot; every write route is blocked."""

import argparse
from pathlib import Path

import uvicorn
from capture_demo_snapshot import outside_git
from fastapi import Request
from fastapi.responses import JSONResponse, Response
from starlette.middleware.base import RequestResponseEndpoint

from weedz.discovery.api import create_app


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", type=Path, required=True)
    parser.add_argument("--port", type=int, default=8312)
    args = parser.parse_args()
    root = outside_git(args.snapshot)
    if not (root / "capture-provenance.json").is_file():
        raise ValueError("Serve only a sanitized copy made by capture_demo_snapshot.py")
    app = create_app(root)

    @app.middleware("http")
    async def read_only(request: Request, call_next: RequestResponseEndpoint) -> Response:
        if request.method not in {"GET", "HEAD"}:
            return JSONResponse(
                {"detail": "The demonstration snapshot is read-only"}, status_code=405
            )
        return await call_next(request)

    uvicorn.run(app, host="127.0.0.1", port=args.port)


if __name__ == "__main__":
    main()
