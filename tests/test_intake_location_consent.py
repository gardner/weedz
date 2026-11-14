"""Exact device locations are received only with explicit location consent."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from intake_helpers import new_id, report

from weedz.intake.api import create_intake_app
from weedz.intake.store import ReportStore
from weedz.intake.submitters import Submitters


@pytest.mark.parametrize("location_present,consented", [(True, False), (False, True)])
def test_location_consent_must_match_the_location(
    tmp_path: Path, location_present: bool, consented: bool
) -> None:
    body = report()
    body["consent"]["location"] = consented
    if not location_present:
        body.pop("location")
    client = TestClient(create_intake_app(tmp_path))
    headers = {"Authorization": f"Bearer {Submitters(tmp_path).issue('Phone').token}"}
    path = f"/reports/{new_id()}"
    assert client.put(path, json=body, headers=headers).status_code == 422
    assert client.get(path, headers=headers).status_code == 404
    assert ReportStore(tmp_path).active() == []


def test_location_consent_is_explicit_and_required(tmp_path: Path) -> None:
    body = report()
    body["consent"].pop("location", None)
    client = TestClient(create_intake_app(tmp_path))
    headers = {"Authorization": f"Bearer {Submitters(tmp_path).issue('Phone').token}"}
    assert client.put(f"/reports/{new_id()}", json=body, headers=headers).status_code == 422
    assert ReportStore(tmp_path).active() == []


@pytest.mark.parametrize("location_present", [True, False])
def test_location_consent_survives_storage(tmp_path: Path, location_present: bool) -> None:
    body = report()
    body["consent"]["location"] = location_present
    if not location_present:
        body.pop("location")
    client = TestClient(create_intake_app(tmp_path))
    headers = {"Authorization": f"Bearer {Submitters(tmp_path).issue('Phone').token}"}
    assert client.put(f"/reports/{new_id()}", json=body, headers=headers).status_code == 201
    [stored] = ReportStore(tmp_path).active()
    assert stored.report.consent.location is location_present
    assert (stored.report.location is not None) is location_present
