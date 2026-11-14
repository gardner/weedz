"""A withdrawal erases a device report from review, and nothing else does (issue #58)."""

import fcntl
import json
from pathlib import Path

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from intake_helpers import jpeg, new_id, report, with_image
from test_device_reports import send, synced
from test_study_surface import body

from weedz.discovery import cli, device_reports
from weedz.discovery.api import create_app
from weedz.discovery.device_reports import RUN_ID
from weedz.discovery.store import Store
from weedz.intake.api import IntakeAPI
from weedz.intake.limits import Limits
from weedz.intake.store import ReportStore


def credited(location: dict) -> dict:
    body = with_image(jpeg(), location=location)
    return body | {"consent": body["consent"] | {"credit": "Aroha Unique"}}


def test_a_report_missing_from_intake_is_not_erased(tmp_path: Path) -> None:
    """A wrong or empty intake folder is not a withdrawal."""
    intake = tmp_path / "intake"
    send(intake, with_image(jpeg()))
    [before] = synced(tmp_path, intake)
    [after] = synced(tmp_path, tmp_path / "elsewhere")
    assert not after["consent"]["withdrawn_at"] and after["latitude"] == -41.27
    assert (tmp_path / "pilot" / after["image_path"]).is_file()
    assert synced(tmp_path, intake) == [after] and after["id"] == before["id"]


def test_a_withdrawal_leaves_no_trace_in_the_database_files(tmp_path: Path) -> None:
    intake = tmp_path / "intake"
    point = {"latitude": -41.271234, "longitude": 173.283456, "accuracy_m": 8}
    report_id = send(intake, credited(location=point))
    synced(tmp_path, intake)
    ReportStore(intake).withdraw(1, report_id)
    synced(tmp_path, intake)
    files = sorted((tmp_path / "pilot").glob("discovery.sqlite3*"))
    raw = b"".join(path.read_bytes() for path in files)
    for detail in (b"Aroha Unique", b"-41.271234", b"173.283456", b"2026-10-01T10:00:00"):
        assert detail not in raw


def test_the_review_database_is_owner_only_once_it_holds_device_reports(tmp_path: Path) -> None:
    intake = tmp_path / "intake"
    send(intake, report())
    synced(tmp_path, intake)
    for path in (tmp_path / "pilot").glob("discovery.sqlite3*"):
        assert path.stat().st_mode & 0o077 == 0, path.name


def test_a_crop_written_while_its_report_is_withdrawn_is_deleted(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    intake = tmp_path / "intake"
    report_id = send(intake, with_image(jpeg()))
    write = device_reports._write_private

    def withdrawn_meanwhile(target: Path, data: bytes) -> None:
        ReportStore(intake).withdraw(1, report_id)
        device_reports._sync(  # bypassing the turn-taking lock, as a safeguard
            Store(tmp_path / "pilot"), ReportStore(intake)
        )
        write(target, data)

    monkeypatch.setattr(device_reports, "_write_private", withdrawn_meanwhile)
    [photo] = synced(tmp_path, intake)
    assert photo["consent"]["withdrawn_at"]
    assert list((tmp_path / "pilot" / "images" / "device").iterdir()) == []


def test_a_consented_crop_that_is_gone_is_not_offered(tmp_path: Path) -> None:
    intake = tmp_path / "intake"
    send(intake, with_image(jpeg()))
    [stored] = ReportStore(intake).active()
    assert stored.image is not None
    stored.image.unlink()
    [photo] = synced(tmp_path, intake)
    assert photo["image_path"] == "" and photo["device"]["image_consent"] is True


def test_without_an_intake_folder_a_stored_device_run_is_not_served(tmp_path: Path) -> None:
    """Withdrawals cannot be checked without intake, so nothing of the run is served."""
    intake = tmp_path / "intake"
    send(intake, with_image(jpeg()))
    [photo] = synced(tmp_path, intake)
    client = TestClient(create_app(tmp_path / "pilot"))
    assert RUN_ID not in [run["id"] for run in client.get("/runs").json()]
    for path in ("", "/package", "/export", f"/photos/{photo['id']}/image"):
        assert client.get(f"/runs/{RUN_ID}{path}").status_code == 404, path


def test_the_cli_syncs_withdrawals_before_reading_the_device_run(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    intake, pilot = tmp_path / "intake", tmp_path / "pilot"
    report_id = send(intake, with_image(jpeg()))
    client = TestClient(create_app(pilot, intake_dir=intake))
    [photo] = client.get(f"/runs/{RUN_ID}").json()["photos"]
    lead = {"action": "selected", "selector": "Ana", "reason": "Gorse by the track"}
    client.post(f"/runs/{RUN_ID}/photos/{photo['id']}/leads", json=lead)
    ReportStore(intake).withdraw(1, report_id)
    out = tmp_path / "out"
    base = ["package", "--run", RUN_ID, "--pilot-dir", str(pilot), "--out", str(out)]
    with pytest.raises(SystemExit, match="--intake-dir"):
        cli.main(base)
    cli.main([*base, "--intake-dir", str(intake)])
    assert "Nothing written" in capsys.readouterr().out
    assert not out.exists()


def test_a_crop_whose_copy_failed_is_copied_again(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    intake = tmp_path / "intake"
    send(intake, with_image(jpeg()))
    write = device_reports._write_private

    def full_disk(target: Path, data: bytes) -> None:
        raise OSError("No space left on device")

    monkeypatch.setattr(device_reports, "_write_private", full_disk)
    with pytest.raises(OSError):
        synced(tmp_path, intake)
    monkeypatch.setattr(device_reports, "_write_private", write)
    [photo] = synced(tmp_path, intake)
    assert (tmp_path / "pilot" / photo["image_path"]).is_file()


def test_a_report_withdrawn_before_it_arrives_never_enters_review(tmp_path: Path) -> None:
    intake = tmp_path / "intake"
    report_id = new_id()
    ReportStore(intake).withdraw(1, report_id, before_arrival=True)
    with pytest.raises(HTTPException, match="410"):
        IntakeAPI(intake, Limits()).accept(1, report_id, json.dumps(report()).encode())
    assert synced(tmp_path, intake) == []


def test_a_crop_no_row_names_is_deleted_on_the_next_sync(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A crash after a withdrawal's erase, before its crop was deleted, is recovered."""
    intake = tmp_path / "intake"
    report_id = send(intake, with_image(jpeg()))
    [photo] = synced(tmp_path, intake)
    crop = tmp_path / "pilot" / photo["image_path"]
    kept = crop.read_bytes()
    ReportStore(intake).withdraw(1, report_id)
    synced(tmp_path, intake)
    crop.write_bytes(kept)  # as if the process died before deleting it
    stray = crop.with_name("device-9-unknown.jpg")
    stray.write_bytes(kept)
    synced(tmp_path, intake)
    assert list(crop.parent.iterdir()) == []


def test_the_device_run_claims_no_historical_query(tmp_path: Path) -> None:
    intake = tmp_path / "intake"
    send(intake, report())
    client = TestClient(create_app(tmp_path / "pilot", intake_dir=intake))
    assert client.get(f"/runs/{RUN_ID}").json()["run"]["spec"] == {}
    suitability = client.get(f"/runs/{RUN_ID}/suitability")
    assert suitability.status_code == 200
    assert "requested photos" not in suitability.text
    dates = suitability.json()["dates"]
    assert dates["query_period"] is None and dates["corpus"]["sampling"] is None
    assert dates["years_without_photos"] == [] and dates["seasons_without_photos"] == []
    assert not any("unassessed, not weed-free" in note for note in dates["notes"])
    # A study period reaching past 2024 is not "outside" a query that never ran.
    study = body(period_start="2020-01-01", period_end="2026-12-31") | {"run_id": RUN_ID}
    assert client.post("/studies", json=study).status_code == 201
    linked = client.get(f"/runs/{RUN_ID}/suitability").json()["dates"]
    assert not any("query period" in note for note in linked["notes"])


def test_syncs_take_turns(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """An older sync never writes after a newer one has applied a withdrawal."""
    intake = tmp_path / "intake"
    send(intake, report())
    listed = ReportStore.active
    held = []

    def while_listing(self: ReportStore) -> list:
        with (tmp_path / "pilot" / device_reports.LOCK).open("a") as other:
            try:
                fcntl.flock(other, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                held.append(True)
        return listed(self)

    monkeypatch.setattr(ReportStore, "active", while_listing)
    synced(tmp_path, intake)
    assert held == [True]


def test_device_reports_are_not_offered_as_reference_examples(tmp_path: Path) -> None:
    intake, pilot = tmp_path / "intake", tmp_path / "pilot"
    send(intake, report())
    synced(tmp_path, intake)
    command = ["reference", "--run", RUN_ID, "--pilot-dir", str(pilot)]
    with pytest.raises(SystemExit, match="not reference examples"):
        cli.main(command)
