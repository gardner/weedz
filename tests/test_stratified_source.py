"""Stratified acquisition queries each season, snapshots it, and downloads only the sample."""

import io
from datetime import date
from pathlib import Path

import httpx
import pytest
from PIL import Image
from test_discovery import observation

from weedz.discovery import source
from weedz.discovery.records import RunSpec
from weedz.discovery.source import Inaturalist


def jpeg() -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (4, 4), (40, 120, 40)).save(buffer, "JPEG")
    return buffer.getvalue()


def test_stratified_run_queries_each_season_and_downloads_only_selected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(source.time, "sleep", lambda _seconds: None)
    queries: list[httpx.QueryParams] = []
    downloads: list[str] = []

    def handle(request: httpx.Request) -> httpx.Response:
        if request.url.host != "api.inaturalist.org":
            downloads.append(str(request.url))
            return httpx.Response(200, content=jpeg())
        params = request.url.params
        queries.append(params)
        if "taxon_name" in params:
            return httpx.Response(200, json={"results": []})
        day = params["d1"]
        results = []
        for offset in range(3):
            raw = observation() | {
                "id": int(day.replace("-", "")) * 10 + offset,
                "observed_on": day,
                "user": {"login": f"{params['place_id']}-{day}-{offset}"},
            }
            raw["photos"] = [raw["photos"][0] | {"id": raw["id"]}]
            results.append(raw)
        return httpx.Response(200, json={"results": results})

    client = Inaturalist(tmp_path)
    client.client = httpx.Client(transport=httpx.MockTransport(handle))
    spec = RunSpec(
        limit_per_region=4,
        controls_per_species=0,
        after=date(2023, 1, 1),
        before=date(2023, 12, 31),
    )
    photos = client.collect("run", spec)

    animal_queries = [q for q in queries if q.get("taxon_id") == "1"]
    assert len(animal_queries) == 2 * 5  # two regions, five season windows
    assert all("d1" in q and "d2" in q for q in animal_queries)
    assert len(photos) == 8
    assert len(downloads) == 8
    assert len({p.observed_on for p in photos if p.region == "Nelson"}) == 4
    snapshots = sorted(path.name for path in (tmp_path / "runs" / "run").glob("*.json"))
    assert "Nelson-animals-2023-MAM.json" in snapshots


def test_recent_sampling_keeps_the_original_single_query(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(source.time, "sleep", lambda _seconds: None)
    queries: list[httpx.QueryParams] = []

    def handle(request: httpx.Request) -> httpx.Response:
        queries.append(request.url.params)
        return httpx.Response(200, json={"results": []})

    client = Inaturalist(tmp_path)
    client.client = httpx.Client(transport=httpx.MockTransport(handle))
    client.collect("run", RunSpec(controls_per_species=0, sampling="recent"))
    assert len(queries) == 2
    assert all("d1" not in q for q in queries)


def test_every_season_query_is_preceded_by_a_heartbeat(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(source.time, "sleep", lambda _seconds: None)
    events: list[str] = []

    def handle(request: httpx.Request) -> httpx.Response:
        events.append(f"query {request.url.params.get('d1')}")
        return httpx.Response(200, json={"results": []})

    client = Inaturalist(tmp_path)
    client.client = httpx.Client(transport=httpx.MockTransport(handle))
    spec = RunSpec(controls_per_species=0, after=date(2022, 1, 1), before=date(2023, 12, 31))
    client.collect("run", spec, progress=lambda message: events.append(f"progress {message}"))

    queries = [index for index, event in enumerate(events) if event.startswith("query")]
    assert len(queries) == 2 * 9  # two regions, nine season windows
    assert all(events[index - 1].startswith("progress Querying") for index in queries)
