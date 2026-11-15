"""Serve the authenticated review API on loopback behind the website proxy."""

import argparse
from pathlib import Path

import uvicorn

from weedz.discovery.api import create_app


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--port", type=int, default=8058)
    args = parser.parse_args()
    root = args.data.resolve()
    if not (root / "discovery.sqlite3").is_file():
        raise SystemExit("Seed the isolated review data before starting the service")
    if not 1024 <= args.port <= 65535:
        raise SystemExit("Choose an unprivileged TCP port")
    uvicorn.run(
        create_app(root, access="tokens"),
        host="127.0.0.1",
        port=args.port,
        access_log=False,
        proxy_headers=False,
    )


if __name__ == "__main__":
    main()
