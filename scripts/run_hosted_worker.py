"""Run the owned hosted pipeline worker with an SDK-managed or configured Temporal service."""

import argparse
import asyncio
import signal
from pathlib import Path

from weedz.discovery.hosted_worker import serve_worker
from weedz.discovery.hosting import HOSTED_NAMESPACE, HOSTED_TASK_QUEUE, TemporalConnection


async def run(args: argparse.Namespace) -> None:
    connection = TemporalConnection(args.temporal_url, args.namespace, args.task_queue, args.tls)
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for received in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(received, stop.set)
    await serve_worker(
        args.data.resolve(),
        connection,
        args.temporal_state,
        args.health_file,
        stop,
        args.temporal_executable,
    )


def main() -> None:
    base = Path.home() / ".local/share/weedz/site"
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument(
        "--temporal-url", help="Configured host:port; omit for an SDK-managed local server"
    )
    parser.add_argument("--namespace", default=HOSTED_NAMESPACE)
    parser.add_argument("--task-queue", default=HOSTED_TASK_QUEUE)
    parser.add_argument("--tls", action="store_true")
    parser.add_argument("--temporal-state", type=Path, default=base / "temporal")
    parser.add_argument("--health-file", type=Path, default=base / "workflows/worker-health.json")
    parser.add_argument(
        "--temporal-executable",
        type=Path,
        help="Optional existing CLI override; no fallback if invalid",
    )
    asyncio.run(run(parser.parse_args()))


if __name__ == "__main__":
    main()
