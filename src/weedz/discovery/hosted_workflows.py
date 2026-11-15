"""Truthful hosted workflow availability, separate from reviewer authentication."""

import asyncio
from dataclasses import dataclass, field
from datetime import timedelta
from pathlib import Path
from typing import Literal

from temporalio.client import Client

from weedz.discovery.hosting import TemporalConnection
from weedz.discovery.records import RunSpec
from weedz.discovery.workflow_health import worker_is_ready

CONNECTION_TIMEOUT_SECONDS = 2


@dataclass
class _LoopClient:
    loop: asyncio.AbstractEventLoop
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    client: Client | None = None


@dataclass
class _ClientCache:
    current: _LoopClient | None = None

    def for_current_loop(self) -> _LoopClient:
        loop = asyncio.get_running_loop()
        if self.current is None or self.current.loop is not loop:
            self.current = _LoopClient(loop)
        return self.current


@dataclass(frozen=True)
class HostedWorkflows:
    connection: TemporalConnection
    health_file: Path
    segmentation_default: Literal["off", "sam2.1-tiny-v1"] = "off"
    _clients: _ClientCache = field(default_factory=_ClientCache, repr=False, compare=False)

    def apply_defaults(self, spec: RunSpec) -> RunSpec:
        if "segmentation" in spec.model_fields_set:
            return spec
        return spec.model_copy(update={"segmentation": self.segmentation_default})

    async def client_if_ready(self) -> Client | None:
        if not worker_is_ready(self.health_file, self.connection):
            return None
        state = self._clients.for_current_loop()
        client: Client | None = None
        try:
            async with asyncio.timeout(CONNECTION_TIMEOUT_SECONDS):
                async with state.lock:
                    if state.client is None:
                        state.client = await Client.connect(
                            self.connection.target,
                            namespace=self.connection.namespace,
                            tls=self.connection.tls,
                        )
                    client = state.client
            if not await client.service_client.check_health(timeout=timedelta(seconds=2)):
                if state.client is client:
                    state.client = None
                return None
            return client if worker_is_ready(self.health_file, self.connection) else None
        except Exception:
            if state.client is client:
                state.client = None
            return None

    async def ready(self) -> bool:
        return await self.client_if_ready() is not None
