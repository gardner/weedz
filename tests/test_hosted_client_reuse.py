"""Availability polls share a loop-local SDK client and reconnect after service failure."""

import asyncio
from types import SimpleNamespace

from weedz.discovery.hosted_workflows import HostedWorkflows
from weedz.discovery.hosting import TemporalConnection
from weedz.discovery.workflow_health import publish_worker_health


def test_concurrent_polls_reuse_one_connection_and_recover_after_failure(tmp_path, monkeypatch):
    connections = []
    healthy = True

    async def check_health(**_kwargs):
        return healthy

    async def connect(*_args, **_kwargs):
        await asyncio.sleep(0)
        client = SimpleNamespace(service_client=SimpleNamespace(check_health=check_health))
        connections.append(client)
        return client

    monkeypatch.setattr("weedz.discovery.hosted_workflows.Client.connect", connect)
    path = tmp_path / "health"
    connection = TemporalConnection()
    publish_worker_health(path, connection, "worker")
    hosted = HostedWorkflows(connection, path)

    async def exercise():
        nonlocal healthy
        assert all(await asyncio.gather(*(hosted.ready() for _ in range(8))))
        assert len(connections) == 1
        healthy = False
        assert await hosted.ready() is False
        healthy = True
        assert await hosted.ready() is True
        assert len(connections) == 2
        path.unlink()
        assert await hosted.ready() is False
        assert len(connections) == 2

    asyncio.run(exercise())


def test_client_is_not_reused_across_event_loops(tmp_path, monkeypatch):
    loops = []

    async def healthy(**_kwargs):
        return True

    async def connect(*_args, **_kwargs):
        loops.append(asyncio.get_running_loop())
        return SimpleNamespace(service_client=SimpleNamespace(check_health=healthy))

    monkeypatch.setattr("weedz.discovery.hosted_workflows.Client.connect", connect)
    connection = TemporalConnection()
    path = tmp_path / "health"
    publish_worker_health(path, connection, "worker")
    hosted = HostedWorkflows(connection, path)
    assert asyncio.run(hosted.ready()) is True
    assert asyncio.run(hosted.ready()) is True
    assert len(loops) == 2 and loops[0] is not loops[1]


def test_concurrent_stalled_connections_have_one_bounded_wait_budget(tmp_path, monkeypatch):
    async def stalled(*_args, **_kwargs):
        await asyncio.sleep(10)

    monkeypatch.setattr("weedz.discovery.hosted_workflows.Client.connect", stalled)
    monkeypatch.setattr(
        "weedz.discovery.hosted_workflows.CONNECTION_TIMEOUT_SECONDS", 0.03, raising=False
    )
    connection = TemporalConnection()
    path = tmp_path / "health"
    publish_worker_health(path, connection, "worker")
    hosted = HostedWorkflows(connection, path)

    async def exercise():
        results = await asyncio.wait_for(
            asyncio.gather(*(hosted.ready() for _ in range(8))), timeout=0.3
        )
        assert results == [False] * 8

    asyncio.run(exercise())
