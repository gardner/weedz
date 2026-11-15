"""Transient health RPC failures revoke readiness without restarting the owned server."""

import asyncio
from collections.abc import Awaitable, Callable
from contextlib import asynccontextmanager
from datetime import timedelta
from types import SimpleNamespace
from typing import cast

import pytest
from temporalio.client import Client
from temporalio.service import RPCError, RPCStatusCode
from test_hosted_worker_shutdown import Activities

from weedz.discovery import hosted_worker
from weedz.discovery.hosting import TemporalConnection
from weedz.discovery.workflow_health import publish_worker_health, worker_is_ready


def fake_client(check_health: Callable[..., Awaitable[bool]]) -> Client:
    return cast(Client, SimpleNamespace(service_client=SimpleNamespace(check_health=check_health)))


@pytest.fixture
def fast_poll(monkeypatch):
    original = asyncio.wait_for

    async def advance(awaitable, timeout):
        if timeout == 5:
            awaitable.close()
            await asyncio.sleep(0)
            raise TimeoutError
        return await original(awaitable, timeout)

    monkeypatch.setattr(hosted_worker.asyncio, "wait_for", advance)


@pytest.mark.parametrize(
    "failure",
    [
        False,
        TimeoutError("health deadline"),
        RPCError("operation was canceled", RPCStatusCode.CANCELLED, b""),
    ],
)
def test_single_health_failure_recovers_without_server_or_worker_teardown(
    tmp_path, monkeypatch, fast_poll, failure
):
    connection, health = TemporalConnection(), tmp_path / "health"
    stop, observed, order = asyncio.Event(), [], []
    outcomes = iter([True, failure, True, True])

    async def check_health(*, timeout):
        assert timeout == timedelta(seconds=2)
        assert order == ["server_start", "worker_start"]
        observed.append(worker_is_ready(health, connection))
        result = next(outcomes)
        if len(observed) == 4:
            stop.set()
        if isinstance(result, BaseException):
            raise result
        return result

    @asynccontextmanager
    async def client(*_args):
        order.append("server_start")
        yield fake_client(check_health)
        order.append("server_stop")

    class Worker:
        async def __aenter__(self):
            order.append("worker_start")

        async def __aexit__(self, *_args):
            assert not worker_is_ready(health, connection)
            order.append("worker_stop")

    (tmp_path / "discovery.sqlite3").touch()
    monkeypatch.setattr(hosted_worker, "Activities", Activities)
    monkeypatch.setattr(hosted_worker, "Worker", lambda *_args, **_kwargs: Worker())
    monkeypatch.setattr(hosted_worker, "temporal_client", client)
    monkeypatch.setattr(hosted_worker, "preflight_models", lambda _: None)
    asyncio.run(hosted_worker.serve_worker(tmp_path, connection, tmp_path / "state", health, stop))
    assert observed == [False, True, False, True]
    assert order == ["server_start", "worker_start", "worker_stop", "server_stop"]
    assert not worker_is_ready(health, connection)


def test_three_consecutive_failures_escalate_without_advertising_readiness(tmp_path, fast_poll):
    connection, health = TemporalConnection(), tmp_path / "health"
    publish_worker_health(health, connection, "owner")
    calls = 0

    async def unhealthy(**_kwargs):
        nonlocal calls
        calls += 1
        if calls > 1:
            assert not worker_is_ready(health, connection)
        return False

    client = fake_client(unhealthy)
    with pytest.raises(RuntimeError, match="3 consecutive"):
        asyncio.run(hosted_worker.heartbeat(client, connection, health, "owner", asyncio.Event()))
    assert calls == 3
    assert not worker_is_ready(health, connection)


def test_success_resets_the_consecutive_failure_streak(tmp_path, fast_poll):
    connection, health = TemporalConnection(), tmp_path / "health"
    stop = asyncio.Event()
    outcomes = iter([False, False, True, False, False, True])
    calls = 0

    async def fluctuating(**_kwargs):
        nonlocal calls
        calls += 1
        if calls == 4:
            assert worker_is_ready(health, connection)
        if calls == 6:
            stop.set()
        return next(outcomes)

    client = fake_client(fluctuating)
    asyncio.run(hosted_worker.heartbeat(client, connection, health, "owner", stop))
    assert calls == 6
    assert not worker_is_ready(health, connection)


def test_cancelled_heartbeat_propagates_cancellation_and_clears_readiness(tmp_path):
    connection, health = TemporalConnection(), tmp_path / "health"
    publish_worker_health(health, connection, "owner")

    async def exercise():
        started = asyncio.Event()

        async def blocked(**_kwargs):
            started.set()
            await asyncio.Event().wait()
            return False

        client = fake_client(blocked)
        task = asyncio.create_task(
            hosted_worker.heartbeat(client, connection, health, "owner", asyncio.Event())
        )
        await started.wait()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    asyncio.run(exercise())
    assert not worker_is_ready(health, connection)


def test_explicit_stop_during_failed_check_exits_without_republishing(tmp_path):
    connection, health = TemporalConnection(), tmp_path / "health"
    stop = asyncio.Event()
    publish_worker_health(health, connection, "owner")

    async def stopping(**_kwargs):
        stop.set()  # The worker's fatal callback uses this same explicit stop signal.
        raise RPCError("operation was canceled", RPCStatusCode.CANCELLED, b"")

    client = fake_client(stopping)
    asyncio.run(hosted_worker.heartbeat(client, connection, health, "owner", stop))
    assert not worker_is_ready(health, connection)


def test_unexpected_health_failure_remains_fatal_and_clears_readiness(tmp_path):
    connection, health = TemporalConnection(), tmp_path / "health"
    publish_worker_health(health, connection, "owner")
    calls = 0

    async def broken(**_kwargs):
        nonlocal calls
        calls += 1
        raise ValueError("Invalid health configuration")

    client = fake_client(broken)
    with pytest.raises(ValueError, match="Invalid health configuration"):
        asyncio.run(hosted_worker.heartbeat(client, connection, health, "owner", asyncio.Event()))
    assert calls == 1
    assert not worker_is_ready(health, connection)
