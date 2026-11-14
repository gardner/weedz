"""One submitter's requests are taken in turn (issue #57): the budget sees every earlier
report before an image is decoded, and a withdrawal never slips past a report being sent."""

import asyncio
import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from intake_helpers import jpeg, new_id, with_image
from starlette.types import Message

from weedz.intake.api import create_intake_app
from weedz.intake.images import clean_image
from weedz.intake.limits import Limits
from weedz.intake.store import ReportStore
from weedz.intake.submitters import Submitters


def token(tmp_path: Path) -> str:
    return Submitters(tmp_path).issue("Pilot phone").token


def test_concurrent_uploads_decode_only_what_the_budget_allows(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    decoded: list[int] = []

    def slow(data: bytes, max_pixels: int) -> bytes:
        decoded.append(len(data))
        time.sleep(0.1)
        return clean_image(data, max_pixels)

    monkeypatch.setattr("weedz.intake.api.clean_image", slow)
    app = create_intake_app(tmp_path, Limits(reports_per_day=1))
    headers = {"Authorization": f"Bearer {token(tmp_path)}"}

    # One client, so every request runs on the same event loop, as under uvicorn.
    with TestClient(app) as client, ThreadPoolExecutor(4) as pool:

        def send(_: int) -> int:
            path = f"/reports/{new_id()}"
            return client.put(path, json=with_image(jpeg()), headers=headers).status_code

        assert sorted(pool.map(send, range(4))) == [201, 429, 429, 429]
    assert len(decoded) == 1


def test_a_withdrawal_during_an_upload_waits_for_it_and_withdraws_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Not a 404 followed by the report being stored anyway."""
    decoding = threading.Event()

    def slow(data: bytes, max_pixels: int) -> bytes:
        decoding.set()
        time.sleep(0.2)
        return clean_image(data, max_pixels)

    monkeypatch.setattr("weedz.intake.api.clean_image", slow)
    headers, path = {"Authorization": f"Bearer {token(tmp_path)}"}, f"/reports/{new_id()}"
    with TestClient(create_intake_app(tmp_path)) as client, ThreadPoolExecutor(1) as pool:
        upload = pool.submit(client.put, path, json=with_image(jpeg()), headers=headers)
        assert decoding.wait(5)
        withdrawn = client.delete(path, headers=headers)
        assert upload.result().status_code == 201
    assert withdrawn.status_code == 200 and withdrawn.json()["status"] == "withdrawn"
    assert ReportStore(tmp_path).active() == []


async def call(app: FastAPI, method: str, path: str, secret: str, parts: list) -> int:
    """Drive the app over raw ASGI, sending the body in ``parts``; an asyncio.Event among
    them holds the rest of the body back until it is set (TestClient sends it at once)."""
    statuses: list[int] = []
    headers = [(b"authorization", f"Bearer {secret}".encode())]
    headers += [(b"content-type", b"application/json")]

    async def receive() -> Message:
        while parts:
            part = parts.pop(0)
            if isinstance(part, asyncio.Event):
                await part.wait()
                continue
            return {"type": "http.request", "body": part, "more_body": bool(parts)}
        if statuses:
            return {"type": "http.disconnect"}
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message: Message) -> None:
        if message["type"] == "http.response.start":
            statuses.append(message["status"])

    scope = {
        "type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1", "method": method,
        "scheme": "http", "path": path, "raw_path": path.encode(), "query_string": b"",
        "root_path": "", "headers": headers, "client": ("127.0.0.1", 1), "server": ("t", 80),
    }  # fmt: skip
    await app(scope, receive, send)
    return statuses[0]


def test_a_withdrawal_while_the_body_is_still_arriving_waits_for_it(tmp_path: Path) -> None:
    """On a slow uplink, receiving the body is most of a PUT; a DELETE then must wait."""
    app, secret, path = create_intake_app(tmp_path), token(tmp_path), f"/reports/{new_id()}"
    body = json.dumps(with_image(jpeg())).encode()

    async def scenario() -> tuple[int, int]:
        rest = asyncio.Event()
        upload = asyncio.create_task(call(app, "PUT", path, secret, [body[:100], rest, body[100:]]))
        await asyncio.sleep(0.1)  # the PUT is waiting for the rest of its body
        withdrawal = asyncio.create_task(call(app, "DELETE", path, secret, []))
        await asyncio.sleep(0.1)
        rest.set()
        return await upload, await withdrawal

    assert asyncio.run(scenario()) == (201, 200)
    assert ReportStore(tmp_path).active() == []
