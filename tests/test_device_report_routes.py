"""Every review-API route treats a withdrawn device report as gone (issues #58, #119).

The routes are walked from the app itself, so a route added later without a case here
fails this test rather than slipping past it.
"""

from pathlib import Path

from fastapi.routing import APIRoute
from fastapi.testclient import TestClient
from intake_helpers import jpeg, with_image
from test_device_reports import send

from weedz.discovery.api import create_app
from weedz.discovery.device_reports import RUN_ID
from weedz.intake.store import ReportStore

PHOTO_PREFIX = "/runs/{run_id}/photos/{photo_id}"
# A valid body for each action, so a refusal is about the photo, not the request.
BODIES = {
    "/review": {"status": "confirmed", "reviewer": "Ana"},
    "/audit": {"finding": "none", "reviewer": "Ana"},
    "/findings": {"kind": "addition", "species": "Ulex europaeus", "reviewer": "Ana"},
    "/judgements": {"dimension": "identity", "value": "confirmed", "reviewer": "Ana"},
    "/leads": {"action": "selected", "selector": "Ana", "reason": "Worth a visit"},
    "/referrals": {"reason": "lookalike", "note": "Check", "referrer": "Ana"},
    "/referrals/{referral_id}/events": {"action": "answered", "actor": "Dr Wiri", "note": "No"},
}
# Run routes that are not about one run's photos.
NOT_ABOUT_PHOTOS = {"/runs/{run_id}/study"}
# Measures of a sampled run's incidental photos, which the device run is not (#123).
SAMPLED_ONLY = {"/runs/{run_id}/outcomes", "/runs/{run_id}/suitability"}


def withdrawn_client(tmp_path: Path) -> tuple[TestClient, str, int]:
    """A client, a withdrawn report's item id, and a referral opened on it beforehand."""
    intake = tmp_path / "intake"
    client = TestClient(create_app(tmp_path / "pilot", intake_dir=intake))
    report_id = send(intake, with_image(jpeg()))
    [photo] = client.get(f"/runs/{RUN_ID}").json()["photos"]
    path = f"/runs/{RUN_ID}/photos/{photo['id']}"
    lead = BODIES["/leads"]
    assert client.post(f"{path}/leads", json=lead).status_code == 200
    referral = client.post(f"{path}/referrals", json=BODIES["/referrals"]).json()["id"]
    ReportStore(intake).withdraw(1, report_id)
    return client, photo["id"], referral


def routes(client: TestClient) -> list[tuple[str, str]]:
    app = client.app
    return [
        (method, route.path)
        for route in app.routes  # type: ignore[attr-defined]
        if isinstance(route, APIRoute) and route.path.startswith("/runs/{run_id}")
        for method in sorted(route.methods or ())
    ]


def test_no_photo_route_shows_or_acts_on_a_withdrawn_report(tmp_path: Path) -> None:
    client, photo_id, referral = withdrawn_client(tmp_path)
    walked = 0
    for method, template in routes(client):
        if not template.startswith(PHOTO_PREFIX):
            continue
        action = template.removeprefix(PHOTO_PREFIX)
        url = template.format(run_id=RUN_ID, photo_id=photo_id, referral_id=referral)
        if method == "POST":
            assert action in BODIES, f"No case for {method} {template}"
            response = client.post(url, json=BODIES[action])
        else:
            response = client.get(url)
        assert response.status_code == 404, f"{method} {template}: {response.text}"
        walked += 1
    assert walked >= 12


def test_no_run_route_mentions_a_withdrawn_report(tmp_path: Path) -> None:
    client, photo_id, _ = withdrawn_client(tmp_path)
    walked = 0
    for method, template in routes(client):
        if method != "GET" or "{photo_id}" in template or template in NOT_ABOUT_PHOTOS:
            continue
        response = client.get(template.format(run_id=RUN_ID))
        expected = 409 if template in SAMPLED_ONLY else 200
        assert response.status_code == expected, f"{template}: {response.text}"
        assert photo_id.encode() not in response.content, template
        walked += 1
    assert walked >= 6
    listed = client.get("/runs").json()
    assert photo_id not in str(listed)
