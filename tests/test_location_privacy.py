"""Exact locations are shared by default; a point a source obscured is never revealed (#61).

Every review-API route that returns data is called for an obscured observation that has
a recorded plant, a judgement, a selected lead, a referral and a nearby reference record.
The displaced point must appear in none of them, whatever the route or format.
"""

import io
import zipfile
from pathlib import Path

from fastapi.testclient import TestClient
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
GET_ROUTES = [
    "/runs",
    "/runs/run",
    "/runs/run/export",
    "/runs/run/outcomes",
    "/runs/run/suitability",
    "/runs/run/study",
    "/runs/run/package",
    "/runs/run/photos/{photo}/reviews",
    "/runs/run/photos/{photo}/findings",
    "/runs/run/photos/{photo}/judgements",
    "/runs/run/photos/{photo}/referrals",
]


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


def test_no_route_reveals_an_obscured_point(tmp_path: Path) -> None:
    client, photo_id = reviewed_lead(tmp_path, **OBSCURED)
    for route in GET_ROUTES:
        response = client.get(route.format(photo=photo_id))
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
