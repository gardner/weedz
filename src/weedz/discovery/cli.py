"""Local stack and bounded pilot commands, invoked through ``uv run main.py``."""

import argparse
import asyncio
import ipaddress
import json
import os
from concurrent.futures import ThreadPoolExecutor
from contextlib import AsyncExitStack, suppress
from datetime import UTC, datetime
from pathlib import Path

import httpx
import uvicorn
from pydantic import ValidationError
from temporalio.client import Client
from temporalio.testing import WorkflowEnvironment
from temporalio.worker import Worker

from weedz.discovery.access import Access
from weedz.discovery.activities import Activities, export
from weedz.discovery.api import create_app
from weedz.discovery.device_reports import RUN_ID as DEVICE_RUN
from weedz.discovery.device_reports import IntakeMismatch, sync
from weedz.discovery.occurrences import fetch_snapshot
from weedz.discovery.outcome_report import to_markdown
from weedz.discovery.outcomes import outcomes
from weedz.discovery.package_output import package_contents, write
from weedz.discovery.package_report import NONE_SELECTED
from weedz.discovery.records import SPECIES, TASK_QUEUE, RunSpec
from weedz.discovery.source import HEADERS
from weedz.discovery.store import Store
from weedz.discovery.study import StudyDefinition, StudyEdit
from weedz.discovery.study_store import (
    AlreadyLinked,
    StaleVersion,
    create_linked,
    run_study,
    save_version,
)
from weedz.discovery.suitability_report import to_markdown as suitability_markdown
from weedz.discovery.workflows import DiscoveryWorkflow
from weedz.intake.store import ReportStore
from weedz.reference import collection
from weedz.reference_report import to_markdown as reference_markdown


async def worker(root: Path, address: str, stack: AsyncExitStack) -> None:
    activities = Activities(root)
    executor = stack.enter_context(ThreadPoolExecutor(max_workers=2))
    await stack.enter_async_context(
        Worker(
            await Client.connect(address),
            task_queue=TASK_QUEUE,
            workflows=[DiscoveryWorkflow],
            activities=activities.registered_activities(),
            activity_executor=executor,
            max_concurrent_activities=1,
        )
    )


def check_binding(access: str, host: str) -> None:
    """Without reviewer tokens, the review app listens only on this computer."""
    loopback = host == "localhost"
    with suppress(ValueError):
        loopback = loopback or ipaddress.ip_address(host).is_loopback
    if access == "local" and not loopback:
        raise SystemExit(
            f"Refusing to serve the review app on {host} without sign-in. Invite reviewers "
            "(uv run main.py reviewers add) and pass --access tokens, behind HTTPS."
        )


async def dev(args: argparse.Namespace) -> None:
    check_binding(args.access, args.web_host)
    root = args.pilot_dir.resolve()
    if args.access == "tokens" and not Access(root).reviewers():
        print("No reviewers invited yet: uv run main.py reviewers add --name NAME", flush=True)
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
                args.web_host,
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
            f"Review: http://{args.web_host}:{args.web_port} ({args.access} access) · "
            f"Temporal: http://127.0.0.1:{args.temporal_ui_port}",
            flush=True,
        )
        server = uvicorn.Server(
            uvicorn.Config(
                create_app(root, address, args.access, args.intake_dir),
                # Only the review app talks to the API, so it never leaves this computer.
                host="127.0.0.1",
                port=args.api_port,
                log_level="info",
            )
        )
        await server.serve()


def api_headers() -> dict[str, str]:
    """A reviewer token from WEEDZ_REVIEWER_TOKEN for an API run with --access tokens. Read
    from the environment, not an option, so it never shows in the process list."""
    token = os.environ.get("WEEDZ_REVIEWER_TOKEN", "").strip()
    return {"Authorization": f"Bearer {token}"} if token else {}


async def discover(args: argparse.Namespace) -> None:
    spec = RunSpec(
        limit_per_region=args.limit,
        controls_per_species=args.controls,
        before=args.before,
        after=args.after,
        sampling=args.sampling,
        lookalikes_per_taxon=args.lookalikes,
        model=args.model,
        screening_backend=getattr(args, "screening_backend", "cpu"),
        segmentation=getattr(args, "segmentation", "off"),
    )
    async with httpx.AsyncClient(timeout=30, headers=api_headers()) as client:
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


def run_store(args: argparse.Namespace) -> Store:
    """The pilot store holding `args.run`; never creates a store where there is none."""
    if not (args.pilot_dir / "discovery.sqlite3").is_file():
        raise SystemExit(f"No pilot store in {args.pilot_dir}")
    store = Store(args.pilot_dir)
    if args.run == DEVICE_RUN:
        sync_device_run(store, args.intake_dir)
    if not any(run["id"] == args.run for run in store.runs()):
        raise SystemExit(f"No run {args.run!r} in {args.pilot_dir}")
    return store


def sync_device_run(store: Store, intake_dir: Path | None) -> None:
    """Device reports change as people withdraw them, so apply withdrawals first (#58)."""
    if intake_dir is None:
        raise SystemExit(
            f"{DEVICE_RUN} holds device reports: pass --intake-dir so withdrawals apply first"
        )
    try:
        sync(store, ReportStore(intake_dir))
    except IntakeMismatch as error:
        raise SystemExit(f"Not read: {error}. Check --intake-dir.") from error


def package(args: argparse.Namespace) -> None:
    """Write the run's follow-up package to a new or empty folder."""
    store = run_store(args)
    if args.out.exists() and not args.out.is_dir():
        raise SystemExit(f"{args.out} is not a folder; choose a new or empty folder")
    if args.out.exists() and any(args.out.iterdir()):
        raise SystemExit(f"{args.out} is not empty; choose a new or empty folder")
    built, photos = package_contents(store, args.run, datetime.now(UTC).isoformat())
    if not built["leads"]:
        print(NONE_SELECTED + " Nothing written.")
        return
    try:
        write(built, photos, args.out)
    except (ValueError, OSError) as error:
        raise SystemExit(f"Package not written: {error}") from error
    count = len(built["leads"])
    print(f"Wrote {count} lead{'s' if count != 1 else ''} for follow-up to {args.out}")


def _print(args: argparse.Namespace, result: dict, markdown: str) -> None:
    """Print the Markdown and, with --json, also write the result there."""
    print(markdown, end="")
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")


def sampled_only(args: argparse.Namespace) -> None:
    """Outcomes and suitability measure a sampled run's incidental photos. Device reports
    are not a sample, so an empty report would mislead."""
    if args.run == DEVICE_RUN:
        raise SystemExit(f"{args.command} is for sampled iNaturalist runs, not {DEVICE_RUN}")


def report(args: argparse.Namespace) -> None:
    sampled_only(args)
    result = outcomes(export(run_store(args), args.run))
    _print(args, result, to_markdown(result))


def suitability(args: argparse.Namespace) -> None:
    sampled_only(args)
    result = export(run_store(args), args.run)["source_suitability"]
    _print(args, result, suitability_markdown(result))


def reference(args: argparse.Namespace) -> None:
    """The run's reviewed examples as a reference collection, with the watchlist's gaps."""
    from weedz.adapters import pilot_samples  # imports PIL, needed by this command only

    if args.run == DEVICE_RUN:
        raise SystemExit(
            "Device reports are not reference examples: their consent and licence are "
            "per report, and the reference collection does not carry them"
        )
    result = collection(args.run, pilot_samples(run_store(args), args.run), SPECIES)
    _print(args, result, reference_markdown(result))


def _record_study(store: Store, args: argparse.Namespace) -> None:
    """Record --file as the run's next study version, refusing an edit whose file is based
    on an older version than the one now standing."""
    if not args.author:
        raise SystemExit("Name who records this study version with --author")
    try:
        definition = StudyDefinition.model_validate_json(args.file.read_text())
    except ValidationError as error:
        raise SystemExit(f"Study not recorded: {error}") from error
    linked = run_study(store, args.run)
    if linked and args.base_version is None:
        raise SystemExit(
            f"This run's study is at version {linked['version']}. Check your file is based "
            f"on it, then pass --base-version {linked['version']}"
        )
    if not linked and args.base_version:
        raise SystemExit(
            "This run has no study yet; record its first version without --base-version"
        )
    edit = StudyEdit(
        definition=definition,
        author=args.author,
        base_version=args.base_version or 0,
        change_note=args.note,
    )
    try:
        if linked:
            save_version(store, linked["id"], edit)
        else:
            # Linked in the same write, so a study someone linked meanwhile is never replaced.
            create_linked(store, args.run, edit)
    except (StaleVersion, AlreadyLinked) as error:
        raise SystemExit(f"Study not recorded: {error}") from error


def study(args: argparse.Namespace) -> None:
    """Show the run's study; with --file, record the file as its next version (a new
    study linked to the run when it has none)."""
    store = run_store(args)
    if args.file:
        _record_study(store, args)
    print(json.dumps(run_study(store, args.run), indent=2, ensure_ascii=False))


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
    local.add_argument(
        "--access",
        choices=["local", "tokens"],
        default="local",
        help="local: self-declared names, this computer only; tokens: invited reviewers sign in",
    )
    local.add_argument(
        "--web-host", default="127.0.0.1", help="Review app address (non-loopback needs tokens)"
    )
    local.add_argument(
        "--intake-dir",
        type=Path,
        help="Review approved device reports received here (uv run main.py intake serve)",
    )
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
    run.add_argument("--screening-backend", choices=["cpu", "cuda-fp32-v1"], default="cpu")
    run.add_argument(
        "--model",
        choices=["bioclip", "bioclip-2"],
        default="bioclip-2",
        help="Pinned screening model (see benchmarks/model-comparison.json)",
    )
    run.add_argument(
        "--segmentation",
        choices=["off", "sam2.1-tiny-v1"],
        default="off",
        help="Optional pinned SAM activities; the connected worker must preflight SAM",
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
    suits = commands.add_parser(
        "suitability", help="Report what a run's photos can and cannot support (Markdown)"
    )
    suits.add_argument("--run", required=True, help="Run id, e.g. nelson-tasman-3e62ad801459")
    suits.add_argument("--pilot-dir", type=Path, default=Path("data/pilot"))
    suits.add_argument("--json", type=Path, help="Also write the summary as JSON here")
    define = commands.add_parser(
        "study", help="Show a run's study, or record a new version of it from a JSON file"
    )
    define.add_argument("--run", required=True, help="Run id, e.g. nelson-tasman-3e62ad801459")
    define.add_argument("--pilot-dir", type=Path, default=Path("data/pilot"))
    define.add_argument("--file", type=Path, help="Study definition JSON to record")
    define.add_argument("--author", help="Who records this version")
    define.add_argument("--note", default="", help="What changed and why")
    define.add_argument(
        "--base-version", type=int, help="The version your file edits (needed once one exists)"
    )
    curate = commands.add_parser(
        "reference",
        help="Report a run's reviewed examples, their eligible uses and gaps (Markdown)",
    )
    curate.add_argument("--run", required=True, help="Run id, e.g. nelson-tasman-3e62ad801459")
    curate.add_argument("--pilot-dir", type=Path, default=Path("data/pilot"))
    curate.add_argument("--json", type=Path, help="Also write the collection as JSON here")
    bundle = commands.add_parser(
        "package", help="Write the follow-up package of a run's selected leads"
    )
    bundle.add_argument("--run", required=True, help="Run id, e.g. nelson-tasman-3e62ad801459")
    bundle.add_argument("--pilot-dir", type=Path, default=Path("data/pilot"))
    bundle.add_argument("--out", type=Path, required=True, help="New or empty folder to write")
    for command in (define, bundle):
        command.add_argument(
            "--intake-dir", type=Path, help=f"Report intake folder, needed for --run {DEVICE_RUN}"
        )
    return parser.parse_args(argv)


def main(argv: list[str]) -> None:
    args = parse(argv)
    reports = {
        "references": references,
        "outcomes": report,
        "suitability": suitability,
        "reference": reference,
        "package": package,
        "study": study,
    }
    if args.command in reports:
        reports[args.command](args)
        return
    asyncio.run(dev(args) if args.command == "dev" else discover(args))
