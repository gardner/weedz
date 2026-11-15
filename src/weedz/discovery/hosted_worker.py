"""One supervised hosted worker; its local SDK server and model instances share its lifetime."""

import asyncio
import os
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from pathlib import Path

from temporalio.client import Client
from temporalio.service import RPCError
from temporalio.worker import Worker

from weedz.discovery.activities import Activities
from weedz.discovery.hosting import TemporalConnection, local_server_command
from weedz.discovery.temporal_runtime import temporal_client
from weedz.discovery.workflow_health import clear_worker_health, publish_worker_health
from weedz.discovery.workflows import DiscoveryWorkflow

HOSTED_LICENCES = frozenset({"cc0", "cc-by"})
MAX_HEALTH_FAILURES = 3


def preflight_models(activities: Activities) -> None:
    """Load the real pinned models before this process advertises readiness."""
    from weedz.discovery.inference import Screener

    activities.preflight_segmentation()
    activities.screeners["bioclip-2"] = Screener.load(
        activities.store.root / "embeddings", model="bioclip-2"
    )


async def heartbeat(
    client: Client,
    connection: TemporalConnection,
    health_file: Path,
    identity: str,
    stop: asyncio.Event,
) -> None:
    failures = 0
    try:
        while not stop.is_set():
            try:
                healthy = await client.service_client.check_health(timeout=timedelta(seconds=2))
            except (RPCError, TimeoutError):
                healthy = False
            if stop.is_set():
                break
            if healthy:
                failures = 0
                publish_worker_health(health_file, connection, identity)
            else:
                clear_worker_health(health_file, identity)
                failures += 1
                if failures >= MAX_HEALTH_FAILURES:
                    raise RuntimeError(f"Temporal health failed {failures} consecutive checks")
            try:
                await asyncio.wait_for(stop.wait(), timeout=5)
            except TimeoutError:
                continue
    finally:
        clear_worker_health(health_file, identity)


async def serve_worker(
    root: Path,
    connection: TemporalConnection,
    temporal_state: Path,
    health_file: Path,
    stop: asyncio.Event,
    executable: Path | None = None,
) -> None:
    if executable is not None and connection.address is None:
        local_server_command(executable, temporal_state, namespace=connection.namespace)
    if not (root / "discovery.sqlite3").is_file():
        raise ValueError("Choose the existing private hosted review data directory")
    activities = Activities(root, allowed_photo_licences=HOSTED_LICENCES)
    await asyncio.to_thread(preflight_models, activities)
    identity = f"weedz-hosted-{os.getpid()}-{uuid.uuid4().hex[:12]}"

    fatal_errors: list[BaseException] = []

    async def fatal(error: BaseException) -> None:
        fatal_errors.append(error)
        stop.set()

    try:
        async with temporal_client(connection, temporal_state, executable) as client:
            with ThreadPoolExecutor(max_workers=2) as executor:
                async with Worker(
                    client,
                    task_queue=connection.task_queue,
                    workflows=[DiscoveryWorkflow],
                    activities=activities.registered_activities(),
                    activity_executor=executor,
                    max_concurrent_activities=1,
                    identity=identity,
                    graceful_shutdown_timeout=timedelta(seconds=30),
                    on_fatal_error=fatal,
                ):
                    try:
                        await heartbeat(client, connection, health_file, identity, stop)
                    finally:
                        # Revoke acceptance before Worker.__aexit__ begins graceful draining.
                        clear_worker_health(health_file, identity)
        if fatal_errors:
            raise RuntimeError("Temporal worker stopped after a fatal error") from fatal_errors[0]
    finally:
        clear_worker_health(health_file, identity)
