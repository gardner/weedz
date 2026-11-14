"""Withdrawal intent survives an upload arriving later, including after restart (#95)."""

from pathlib import Path

from fastapi.testclient import TestClient
from intake_helpers import new_id, report

from weedz.intake.api import create_intake_app
from weedz.intake.limits import Limits
from weedz.intake.store import ReportStore
from weedz.intake.submitters import Submitters


def auth(root: Path, label: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {Submitters(root).issue(label).token}"}


def test_device_withdrawal_before_arrival_survives_restart(tmp_path: Path) -> None:
    headers = auth(tmp_path, "Phone")
    path = f"/reports/{new_id()}"
    client = TestClient(create_intake_app(tmp_path))
    withdrawn = client.delete(path, headers=headers)
    assert withdrawn.status_code == 200
    receipt = withdrawn.json()
    assert receipt["status"] == "withdrawn"
    assert receipt["withdrawn_at"] and not receipt["image"]

    restarted = TestClient(create_intake_app(tmp_path))
    assert restarted.delete(path, headers=headers).json() == receipt
    assert restarted.get(path, headers=headers).json() == receipt
    for _ in range(2):
        assert restarted.put(path, json=report(), headers=headers).status_code == 410
    assert ReportStore(tmp_path).active() == []


def test_early_withdrawal_is_scoped_to_the_authenticated_submitter(tmp_path: Path) -> None:
    owner, other = auth(tmp_path, "Owner"), auth(tmp_path, "Other")
    client = TestClient(create_intake_app(tmp_path))
    path = f"/reports/{new_id()}"
    assert client.delete(path, headers=other).status_code == 200
    assert client.put(path, json=report(), headers=owner).status_code == 201
    assert client.put(path, json=report(), headers=other).status_code == 410
    assert client.get(path, headers=owner).json()["status"] == "received"
    assert len(ReportStore(tmp_path).active()) == 1


def test_new_tombstones_are_bounded_but_existing_withdrawals_are_always_allowed(
    tmp_path: Path,
) -> None:
    headers = auth(tmp_path, "Phone")
    client = TestClient(create_intake_app(tmp_path, Limits(reports_per_day=2)))
    received, early, excess = (f"/reports/{new_id()}" for _ in range(3))
    assert client.put(received, json=report(), headers=headers).status_code == 201
    assert client.delete(early, headers=headers).status_code == 200
    refused = client.delete(excess, headers=headers)
    assert refused.status_code == 429
    assert int(refused.headers["Retry-After"]) > 0
    assert client.get(excess, headers=headers).status_code == 404
    assert client.delete(early, headers=headers).status_code == 200
    assert client.delete(received, headers=headers).status_code == 200
    assert client.put(early, json=report(), headers=headers).status_code == 410
    assert ReportStore(tmp_path).active() == []
