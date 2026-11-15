import asyncio
import json

import httpx
import pytest

from weedz.discovery import cli


@pytest.mark.parametrize("profile", ["off", "sam2.1-tiny-v1"])
def test_discover_transmits_explicit_segmentation_profile(monkeypatch, profile):
    payloads = []

    def response(request):
        payloads.append(json.loads(request.content))
        return httpx.Response(200, json={"id": "test-run"})

    client_type = httpx.AsyncClient
    monkeypatch.setattr(
        cli.httpx,
        "AsyncClient",
        lambda **kwargs: client_type(transport=httpx.MockTransport(response), **kwargs),
    )
    args = cli.parse(["discover", "--segmentation", profile])
    asyncio.run(cli.discover(args))
    assert payloads[0]["segmentation"] == profile


def test_discover_default_profile_remains_off():
    assert cli.parse(["discover"]).segmentation == "off"
