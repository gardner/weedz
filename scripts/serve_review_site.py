"""Serve the authenticated review API on loopback behind the website proxy."""

import argparse
from pathlib import Path

import uvicorn

from weedz.discovery.api import create_app
from weedz.discovery.hosted_workflows import HostedWorkflows
from weedz.discovery.hosting import HOSTED_NAMESPACE, HOSTED_TASK_QUEUE, TemporalConnection


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--port", type=int, default=8058)
    parser.add_argument(
        "--temporal-url", help="Configured host:port; omit for the owned local worker service"
    )
    parser.add_argument("--namespace", default=HOSTED_NAMESPACE)
    parser.add_argument("--task-queue", default=HOSTED_TASK_QUEUE)
    parser.add_argument("--tls", action="store_true")
    parser.add_argument(
        "--worker-health",
        type=Path,
        default=Path.home() / ".local/share/weedz/site/workflows/worker-health.json",
    )
    parser.add_argument("--segmentation-default", choices=["off", "sam2.1-tiny-v1"], default="off")
    args = parser.parse_args()
    root = args.data.resolve()
    if not (root / "discovery.sqlite3").is_file():
        raise SystemExit("Seed the isolated review data before starting the service")
    if not 1024 <= args.port <= 65535:
        raise SystemExit("Choose an unprivileged TCP port")
    connection = TemporalConnection(args.temporal_url, args.namespace, args.task_queue, args.tls)
    hosted = HostedWorkflows(connection, args.worker_health, args.segmentation_default)
    uvicorn.run(
        create_app(root, access="tokens", hosted_workflows=hosted),
        host="127.0.0.1",
        port=args.port,
        access_log=False,
        proxy_headers=False,
    )


if __name__ == "__main__":
    main()
