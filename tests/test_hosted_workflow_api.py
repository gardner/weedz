"""Hosted collection availability requires both the owned worker and Temporal service."""

import asyncio
from types import SimpleNamespace

from fastapi.testclient import TestClient

from weedz.discovery.access import Access
from weedz.discovery.api import create_app
from weedz.discovery.hosted_workflows import HostedWorkflows
from weedz.discovery.hosting import TemporalConnection
from weedz.discovery.workflow_health import publish_worker_health


def test_listening_server_without_worker_never_enables_or_queues_work(tmp_path, monkeypatch):
    async def unexpected_connect(*args, **kwargs):
        raise AssertionError("A missing worker must fail before connecting to Temporal")

    monkeypatch.setattr("weedz.discovery.hosted_workflows.Client.connect", unexpected_connect)
    hosted = HostedWorkflows(TemporalConnection(), tmp_path / "private/worker.json")
    client = TestClient(create_app(tmp_path, access="tokens", hosted_workflows=hosted))
    assert client.get("/session").status_code == 401
    token = Access(tmp_path).invite("Reviewer").token
    headers = {"Authorization": f"Bearer {token}"}
    assert client.get("/session", headers=headers).json()["can_start_runs"] is False
    response = client.post("/runs", json={}, headers=headers)
    assert response.status_code == 503
    assert client.get("/runs", headers=headers).json() == []


def test_worker_marker_without_reachable_server_is_unavailable(tmp_path, monkeypatch):
    async def failed_connect(*args, **kwargs):
        raise ConnectionError("Service unavailable")

    monkeypatch.setattr("weedz.discovery.hosted_workflows.Client.connect", failed_connect)
    path = tmp_path / "private/worker.json"
    connection = TemporalConnection()
    publish_worker_health(path, connection, "test-worker")
    hosted = HostedWorkflows(connection, path)
    assert asyncio.run(hosted.ready()) is False


def test_ready_hosted_start_uses_its_namespace_and_dedicated_queue(tmp_path, monkeypatch):
    calls = []

    async def healthy(**kwargs):
        return True

    async def start(*args, **kwargs):
        calls.append((args, kwargs))

    async def connect(address, **kwargs):
        assert address == "127.0.0.1:7258"
        assert kwargs["namespace"] == "weedz-hosted"
        return SimpleNamespace(
            service_client=SimpleNamespace(check_health=healthy), start_workflow=start
        )

    monkeypatch.setattr("weedz.discovery.hosted_workflows.Client.connect", connect)
    path = tmp_path / "private/worker.json"
    connection = TemporalConnection()
    publish_worker_health(path, connection, "test-worker")
    hosted = HostedWorkflows(connection, path)
    client = TestClient(create_app(tmp_path, access="tokens", hosted_workflows=hosted))
    headers = {"Authorization": f"Bearer {Access(tmp_path).invite('Reviewer').token}"}
    assert client.get("/session", headers=headers).json()["can_start_runs"] is True
    response = client.post("/runs", json={}, headers=headers)
    assert response.status_code == 202
    assert calls[0][1]["task_queue"] == "weedz-hosted-discovery-v2"
    assert calls[0][1]["id"] == response.json()["id"]
    assert len(client.get("/runs", headers=headers).json()) == 1
