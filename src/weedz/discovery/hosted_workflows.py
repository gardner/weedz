"""Truthful hosted workflow availability, separate from reviewer authentication."""

import asyncio
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path

from temporalio.client import Client

from weedz.discovery.hosting import TemporalConnection
from weedz.discovery.workflow_health import worker_is_ready


@dataclass(frozen=True)
class HostedWorkflows:
    connection: TemporalConnection
    health_file: Path

    async def client_if_ready(self) -> Client | None:
        if not worker_is_ready(self.health_file, self.connection):
            return None
        try:
            client = await asyncio.wait_for(
                Client.connect(
                    self.connection.target,
                    namespace=self.connection.namespace,
                    tls=self.connection.tls,
                ),
                timeout=2,
            )
            if not await client.service_client.check_health(timeout=timedelta(seconds=2)):
                return None
            return client if worker_is_ready(self.health_file, self.connection) else None
        except Exception:
            return None

    async def ready(self) -> bool:
        return await self.client_if_ready() is not None
