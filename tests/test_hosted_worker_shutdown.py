"""Readiness is revoked before graceful draining can stop polling for thirty seconds."""

import asyncio
from contextlib import asynccontextmanager

import pytest

from weedz.discovery.hosted_worker import serve_worker
from weedz.discovery.hosting import TemporalConnection


class Activities:
    def __init__(self, *_args, **_kwargs):
        pass

    def registered_activities(self):
        return []


class DrainingWorker:
    def __init__(self, order):
        self.order = order

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        self.order.append("drain")
        assert "clear" in self.order, "Readiness remained published during graceful drain"


@asynccontextmanager
async def client(*_args):
    yield object()


@pytest.mark.parametrize("failed", [False, True])
def test_readiness_clears_before_worker_context_drains(monkeypatch, tmp_path, failed):
    order = []
    (tmp_path / "discovery.sqlite3").touch()

    async def heartbeat(*_args):
        order.append("ready")
        if failed:
            raise RuntimeError("Service lost")

    monkeypatch.setattr("weedz.discovery.hosted_worker.Activities", Activities)
    monkeypatch.setattr(
        "weedz.discovery.hosted_worker.Worker", lambda *_args, **_kwargs: DrainingWorker(order)
    )
    monkeypatch.setattr("weedz.discovery.hosted_worker.temporal_client", client)
    monkeypatch.setattr("weedz.discovery.hosted_worker.preflight_models", lambda _: None)
    monkeypatch.setattr("weedz.discovery.hosted_worker.heartbeat", heartbeat)
    monkeypatch.setattr(
        "weedz.discovery.hosted_worker.clear_worker_health", lambda *_: order.append("clear")
    )
    call = serve_worker(
        tmp_path, TemporalConnection(), tmp_path / "state", tmp_path / "health", asyncio.Event()
    )
    if failed:
        with pytest.raises(RuntimeError, match="Service lost"):
            asyncio.run(call)
    else:
        asyncio.run(call)
    assert order[:3] == ["ready", "clear", "drain"]
