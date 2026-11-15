"""Own a persisted local SDK server, or connect to an explicitly configured service."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from temporalio.client import Client
from temporalio.testing import WorkflowEnvironment

from weedz.discovery.hosting import TemporalConnection, local_server_command

CLI_DOWNLOAD_VERSION = "default"


@asynccontextmanager
async def temporal_client(
    connection: TemporalConnection,
    state: Path,
    executable: Path | None = None,
) -> AsyncIterator[Client]:
    if connection.address is not None:
        yield await Client.connect(
            connection.address, namespace=connection.namespace, tls=connection.tls
        )
        return
    # An explicitly configured executable never silently falls back to a download.
    if executable is not None:
        local_server_command(executable, state, namespace=connection.namespace)
    state = state.expanduser().resolve()
    if state.exists() and state.stat().st_mode & 0o077:
        raise ValueError("Temporal state must be in an owner-private directory")
    state.mkdir(mode=0o700, parents=True, exist_ok=True)
    cache = state / "runtime"
    cache.mkdir(mode=0o700, exist_ok=True)
    async with await WorkflowEnvironment.start_local(
        namespace=connection.namespace,
        ip="127.0.0.1",
        port=7258,
        ui=False,
        download_dest_dir=str(cache),
        dev_server_download_version=CLI_DOWNLOAD_VERSION,
        dev_server_database_filename=str(state / "temporal.sqlite3"),
        dev_server_existing_path=str(executable.resolve()) if executable is not None else None,
    ) as environment:
        yield environment.client
