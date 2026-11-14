"""Exact locations are shared by default; a point a source obscured is never revealed (#61).

Every review-API route that returns data is called for an obscured observation that has
a recorded plant, a judgement, a selected lead, a referral and a nearby reference record.
The displaced point must appear in none of them, whatever the route or format.
"""

import io
import zipfile
from pathlib import Path

from fastapi.testclient import TestClient
from starlette.routing import Route
from test_judgements import (
    PUBLIC,
    SCREENED,
    add_finding,
    load_references,
    nearby,
    save,
    store_with_photo,
)
from test_leads import select
from test_referrals import refer

from weedz.discovery.api import create_app

# Distinctive digits, so a match can only be this point.
OBSCURED = {"location": "-41.27391,173.28417", "positional_accuracy": 7}
DIGITS = ("41.27391", "173.28417")
CHECKED = {
    "/runs",
    "/runs/{run_id}",
    "/runs/{run_id}/export",
    "/runs/{run_id}/outcomes",
    "/runs/{run_id}/suitability",
    "/runs/{run_id}/study",
    "/runs/{run_id}/package",
    "/runs/{run_id}/photos/{photo_id}/reviews",
    "/runs/{run_id}/photos/{photo_id}/findings",
    "/runs/{run_id}/photos/{photo_id}/judgements",
    "/runs/{run_id}/photos/{photo_id}/referrals",
}
# Every other GET route, with why it cannot carry a photo's location as text.
EXEMPT = {
    "/session": "who is signed in; no photo data",
    "/studies": "study definitions; no photos",
    "/studies/terms": "study vocabulary; no photos",
    "/studies/{study_id}": "a study definition; no photos",
    "/runs/{run_id}/package/archive": "unpacked and checked by archive_text",
    "/runs/{run_id}/photos/{photo_id}/image": "image bytes: iNaturalist strips hosted "
    "photos' metadata (docs/datasets.md), and device crops are re-encoded (#57)",
    "/openapi.json": "the API schema",
    "/docs": "the API docs page",
    "/docs/oauth2-redirect": "the API docs page",
    "/redoc": "the API docs page",
}


def reviewed_lead(root: Path, **fields: object) -> tuple[TestClient, str]:
    """A screened photo with every kind of review evidence, and a record near it."""
    load_references(root, records=[nearby(2020) | {"latitude": -41.274, "longitude": 173.284}])
    store, photo_id = store_with_photo(root, SCREENED, **fields)
    store.review("run", photo_id, "confirmed", "", "Ana")
    add_finding(store, photo_id)
    save(store, photo_id)
    select(store, photo_id)
    refer(store, photo_id)
    return TestClient(create_app(root)), photo_id


def archive_text(client: TestClient) -> str:
    response = client.get("/runs/run/package/archive")
    assert response.status_code == 200
    with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
        return "\n".join(
            archive.read(name).decode()
            for name in archive.namelist()
            if name.endswith((".json", ".md"))
        )


def test_every_get_route_is_checked_or_exempted_with_a_reason(tmp_path: Path) -> None:
    """A new GET route fails here until someone decides whether it can carry a point."""
    served = {
        route.path
        for route in create_app(tmp_path).routes
        if isinstance(route, Route) and "GET" in (route.methods or ())
    }
    assert served == CHECKED | set(EXEMPT)


def test_no_route_reveals_an_obscured_point(tmp_path: Path) -> None:
    client, photo_id = reviewed_lead(tmp_path, **OBSCURED)
    for route in sorted(CHECKED):
        response = client.get(route.format(run_id="run", photo_id=photo_id))
        assert response.status_code == 200, route
        assert not any(digits in response.text for digits in DIGITS), route
    assert not any(digits in archive_text(client) for digits in DIGITS)


def test_an_obscured_point_never_gains_a_precision_or_a_search_area(tmp_path: Path) -> None:
    client, _photo_id = reviewed_lead(tmp_path, **OBSCURED)
    [photo] = client.get("/runs/run/export").json()["photos"]
    assert photo["sharing"]["location"]["withheld"].startswith("Withheld: the source obscured")
    area = photo["limits"]["search_area"]
    assert (area["status"], area["centre"], area["radius_m"]) == ("obscured", None, None)
    [lead] = client.get("/runs/run/package").json()["leads"]
    assert lead["comparison"]["records_near_photo"]["comparable"] is False


def test_a_public_point_is_shared_exactly_with_its_accuracy(tmp_path: Path) -> None:
    client, _photo_id = reviewed_lead(tmp_path, **OBSCURED | PUBLIC)
    [photo] = client.get("/runs/run/export").json()["photos"]
    assert (photo["latitude"], photo["longitude"]) == (-41.27391, 173.28417)
    assert photo["positional_accuracy_m"] == 7
    [lead] = client.get("/runs/run/package").json()["leads"]
    assert lead["limits"]["search_area"]["centre"] == [-41.27391, 173.28417]
    assert all(digits in archive_text(client) for digits in DIGITS)
