"""The worker owns an SDK-managed local server only when no URL is configured."""

import asyncio
from contextlib import AbstractAsyncContextManager
from types import SimpleNamespace

from weedz.discovery.hosting import TemporalConnection
from weedz.discovery.temporal_runtime import temporal_client


def test_no_address_starts_sdk_server_with_private_persistent_state(tmp_path, monkeypatch):
    calls = []
    client = object()

    class Environment(AbstractAsyncContextManager):
        async def __aenter__(self):
            return SimpleNamespace(client=client)

        async def __aexit__(self, *args):
            calls.append("stopped")

    async def start_local(**kwargs):
        calls.append(kwargs)
        return Environment()

    monkeypatch.setattr(
        "weedz.discovery.temporal_runtime.WorkflowEnvironment.start_local", start_local
    )

    async def run():
        async with temporal_client(TemporalConnection(), tmp_path / "state") as connected:
            assert connected is client

    asyncio.run(run())
    assert calls[0]["ip"] == "127.0.0.1"
    assert calls[0]["ui"] is False
    assert calls[0]["namespace"] == "weedz-hosted"
    assert calls[0]["dev_server_database_filename"] == str(tmp_path / "state/temporal.sqlite3")
    assert calls[-1] == "stopped"
    assert (tmp_path / "state").stat().st_mode & 0o077 == 0


def test_configured_endpoint_never_starts_or_downloads_a_server(tmp_path, monkeypatch):
    calls = []
    client = object()

    async def connect(address, **kwargs):
        calls.append((address, kwargs))
        return client

    async def no_local(**kwargs):
        raise AssertionError("An external service must not start a local server")

    monkeypatch.setattr("weedz.discovery.temporal_runtime.Client.connect", connect)
    monkeypatch.setattr(
        "weedz.discovery.temporal_runtime.WorkflowEnvironment.start_local", no_local
    )

    async def run():
        connection = TemporalConnection(address="temporal.example.org:7233", tls=True)
        async with temporal_client(connection, tmp_path / "unused") as connected:
            assert connected is client

    asyncio.run(run())
    assert calls == [("temporal.example.org:7233", {"namespace": "weedz-hosted", "tls": True})]
    assert not (tmp_path / "unused").exists()
