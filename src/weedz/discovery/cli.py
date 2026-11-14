"""Local stack and bounded pilot commands, invoked through ``uv run main.py``."""

import argparse
import asyncio
import json
import os
from concurrent.futures import ThreadPoolExecutor
from contextlib import AsyncExitStack
from datetime import UTC, datetime
from pathlib import Path

import httpx
import uvicorn
from temporalio.client import Client
from temporalio.testing import WorkflowEnvironment
from temporalio.worker import Worker

from weedz.discovery.activities import Activities, export
from weedz.discovery.api import create_app
from weedz.discovery.occurrences import fetch_snapshot
from weedz.discovery.outcome_report import to_markdown
from weedz.discovery.outcomes import outcomes
from weedz.discovery.records import TASK_QUEUE, RunSpec
from weedz.discovery.source import HEADERS
from weedz.discovery.store import Store
from weedz.discovery.workflows import DiscoveryWorkflow


async def worker(root: Path, address: str, stack: AsyncExitStack) -> None:
    activities = Activities(root)
    executor = stack.enter_context(ThreadPoolExecutor(max_workers=2))
    await stack.enter_async_context(
        Worker(
            await Client.connect(address),
            task_queue=TASK_QUEUE,
            workflows=[DiscoveryWorkflow],
            activities=[
                activities.collect_photos,
                activities.screen_photos,
                activities.export_run,
                activities.fail_run,
            ],
            activity_executor=executor,
            max_concurrent_activities=1,
        )
    )


async def dev(args: argparse.Namespace) -> None:
    root = args.pilot_dir.resolve()
    root.mkdir(parents=True, exist_ok=True)
    async with AsyncExitStack() as stack:
        await stack.enter_async_context(
            await WorkflowEnvironment.start_local(
                ip="127.0.0.1",
                port=args.temporal_port,
                ui=True,
                ui_port=args.temporal_ui_port,
                dev_server_database_filename=str(root / "temporal.sqlite3"),
            )
        )
        address = f"localhost:{args.temporal_port}"
        await worker(root, address, stack)
        if not args.no_web:
            web = Path(__file__).resolve().parents[3] / "web"
            process = await asyncio.create_subprocess_exec(
                "pnpm",
                "exec",
                "next",
                "dev",
                "--hostname",
                "127.0.0.1",
                "--port",
                str(args.web_port),
                cwd=web,
                env=os.environ
                | {
                    "WEEDZ_API_URL": f"http://127.0.0.1:{args.api_port}",
                    "NEXT_PUBLIC_TEMPORAL_UI_URL": f"http://127.0.0.1:{args.temporal_ui_port}",
                },
            )

            async def stop_web() -> None:
                if process.returncode is None:
                    process.terminate()
                    await process.wait()

            stack.push_async_callback(stop_web)
        print(
            f"Review: http://127.0.0.1:{args.web_port} · "
            f"Temporal: http://127.0.0.1:{args.temporal_ui_port}",
            flush=True,
        )
        server = uvicorn.Server(
            uvicorn.Config(
                create_app(root, address),
                host="127.0.0.1",
                port=args.api_port,
                log_level="info",
            )
        )
        await server.serve()


async def discover(args: argparse.Namespace) -> None:
    spec = RunSpec(
        limit_per_region=args.limit,
        controls_per_species=args.controls,
        before=args.before,
        after=args.after,
        sampling=args.sampling,
        lookalikes_per_taxon=args.lookalikes,
        model=args.model,
    )
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(f"{args.api_url}/runs", json=spec.model_dump(mode="json"))
        response.raise_for_status()
        run_id = response.json()["id"]
    print(f"Started {run_id}. Follow in the review app or Temporal UI.", flush=True)
    if args.wait:
        client = await Client.connect(args.temporal_address)
        result = await client.get_workflow_handle(run_id).result()
        print(json.dumps(result, indent=2))


def references(args: argparse.Namespace) -> None:
    with httpx.Client(headers=HEADERS, timeout=60) as client:
        path = fetch_snapshot(args.pilot_dir, client, datetime.now(UTC))
    print(f"Wrote reference snapshot {path}")


def report(args: argparse.Namespace) -> None:
    if not (args.pilot_dir / "discovery.sqlite3").is_file():
        raise SystemExit(f"No pilot store in {args.pilot_dir}")
    store = Store(args.pilot_dir)
    if not any(run["id"] == args.run for run in store.runs()):
        raise SystemExit(f"No run {args.run!r} in {args.pilot_dir}")
    result = outcomes(export(store, args.run))
    print(to_markdown(result), end="")
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")


def parse(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Nelson/Tasman discovery and review")
    commands = parser.add_subparsers(dest="command", required=True)
    local = commands.add_parser(
        "dev", help="Start persistent local Temporal, worker, API and Next.js"
    )
    local.add_argument("--pilot-dir", type=Path, default=Path("data/pilot"))
    local.add_argument("--api-port", type=int, default=8000)
    local.add_argument("--web-port", type=int, default=3001)
    local.add_argument("--temporal-port", type=int, default=7234)
    local.add_argument("--temporal-ui-port", type=int, default=8234)
    local.add_argument("--no-web", action="store_true")
    run = commands.add_parser("discover", help="Queue a bounded historical regional run")
    run.add_argument(
        "--limit", type=int, default=12, help="Animal-subject photos per region (1–50)"
    )
    run.add_argument(
        "--controls", type=int, default=1, help="References per species per region (0–3)"
    )
    run.add_argument("--before", default="2024-12-31")
    run.add_argument("--after", default="2010-01-01", help="Earliest observed date")
    run.add_argument(
        "--sampling",
        choices=["stratified", "recent"],
        default="stratified",
        help="Spread across seasons and observers, or reproduce newest-first selection",
    )
    run.add_argument("--api-url", default="http://127.0.0.1:8000")
    run.add_argument("--temporal-address", default="localhost:7234")
    run.add_argument("--wait", action="store_true")
    run.add_argument(
        "--lookalikes",
        type=int,
        default=0,
        help="Lookalike photos per declared lookalike taxon per region (0–3)",
    )
    run.add_argument(
        "--model",
        choices=["bioclip", "bioclip-2"],
        default="bioclip-2",
        help="Pinned screening model (see benchmarks/model-comparison.json)",
    )
    snapshot = commands.add_parser(
        "references", help="Snapshot DOC weed records from GBIF for distance comparison"
    )
    snapshot.add_argument("--pilot-dir", type=Path, default=Path("data/pilot"))
    measures = commands.add_parser(
        "outcomes", help="Report a run against the pilot success measures (Markdown)"
    )
    measures.add_argument("--run", required=True, help="Run id, e.g. nelson-tasman-3e62ad801459")
    measures.add_argument("--pilot-dir", type=Path, default=Path("data/pilot"))
    measures.add_argument("--json", type=Path, help="Also write the report as JSON here")
    return parser.parse_args(argv)


def main(argv: list[str]) -> None:
    args = parse(argv)
    if args.command == "references":
        references(args)
        return
    if args.command == "outcomes":
        report(args)
        return
    asyncio.run(dev(args) if args.command == "dev" else discover(args))
