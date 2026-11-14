"""A durable deletion barrier covers uploads already authenticated elsewhere (#101)."""

import json
import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from intake_helpers import jpeg, new_id, report, with_image

from weedz.intake.api import create_intake_app
from weedz.intake.deletion import Deletions
from weedz.intake.limits import Limits
from weedz.intake.schema import Report
from weedz.intake.store import ReportStore, Withdrawn
from weedz.intake.submitters import Submitters


def test_delete_all_erases_only_the_authenticated_submitter(tmp_path: Path) -> None:
    first, second = Submitters(tmp_path).issue("first"), Submitters(tmp_path).issue("second")
    client = TestClient(create_intake_app(tmp_path))
    headers = {"Authorization": f"Bearer {first.token}"}
    other = {"Authorization": f"Bearer {second.token}"}
    report_id = new_id()
    assert (
        client.put(f"/reports/{report_id}", json=with_image(jpeg()), headers=headers).status_code
        == 201
    )
    assert client.put(f"/reports/{report_id}", json=report(), headers=other).status_code == 201

    deleted = client.delete("/submitter", headers=headers)
    assert deleted.status_code == 200
    assert deleted.json()["status"] == "deleted"
    assert client.delete("/submitter", headers=headers).json() == deleted.json()
    assert client.put(f"/reports/{new_id()}", json=report(), headers=headers).status_code == 401
    assert client.get(f"/reports/{report_id}", headers=other).status_code == 200
    assert [item.submitter for item in ReportStore(tmp_path).active()] == [second.id]
    assert not list((tmp_path / "reports/images").iterdir())
    with sqlite3.connect(tmp_path / "reports/reports.sqlite3") as db:
        assert db.execute(
            "SELECT body,content_sha256,image_file,withdrawn_at FROM reports WHERE submitter=?",
            (first.id,),
        ).fetchone() == (None, None, None, deleted.json()["requested_at"])


def test_pending_deletion_blocks_inflight_and_survives_restart(tmp_path: Path) -> None:
    credential = Submitters(tmp_path).issue("phone")
    report_id, limits = new_id(), Limits()
    store = ReportStore(tmp_path)
    body = Report.model_validate_json(json.dumps(report()))
    assert store.admit(credential.id, report_id, "digest", False, limits) is None
    deletions = Deletions(tmp_path)
    deletions.begin(credential.id)
    # A different store models a worker that authenticated before deletion began.
    with pytest.raises(Withdrawn):
        ReportStore(tmp_path).receive(credential.id, report_id, body, "digest", None, limits)
    with pytest.raises(Withdrawn):
        ReportStore(tmp_path).admit(credential.id, new_id(), "digest", False, limits)
    create_intake_app(tmp_path)
    assert Submitters(tmp_path).submitter(credential.token) is None
    receipt = Deletions(tmp_path).delete(credential.id)
    assert receipt.status == "deleted"
    assert receipt.completed_at is not None


def test_revocation_does_not_grant_a_new_deletion_capability(tmp_path: Path) -> None:
    credential = Submitters(tmp_path).issue("phone")
    client = TestClient(create_intake_app(tmp_path))
    Submitters(tmp_path).revoke(credential.id)
    assert (
        client.delete(
            "/submitter", headers={"Authorization": f"Bearer {credential.token}"}
        ).status_code
        == 401
    )


def test_failure_during_erasure_keeps_barrier_and_retries(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    credential = Submitters(tmp_path).issue("phone")
    client = TestClient(create_intake_app(tmp_path))
    headers = {"Authorization": f"Bearer {credential.token}"}
    assert (
        client.put(f"/reports/{new_id()}", json=with_image(jpeg()), headers=headers).status_code
        == 201
    )
    deletions = Deletions(tmp_path)

    def interrupted() -> None:
        raise OSError("simulated image-directory sync failure")

    with monkeypatch.context() as patch:
        patch.setattr(deletions.store, "_sync_images", interrupted)
        with pytest.raises(OSError):
            deletions.delete(credential.id)
    assert not ReportStore(tmp_path).active()
    assert Submitters(tmp_path).submitter(credential.token) is None
    # The barrier committed separately: restart finishes erasure despite the rollback.
    restarted = TestClient(create_intake_app(tmp_path))
    assert restarted.delete("/submitter", headers=headers).json()["status"] == "deleted"
    with sqlite3.connect(tmp_path / "reports/reports.sqlite3") as db:
        assert db.execute("SELECT body,image_file FROM reports").fetchone() == (None, None)


def test_deletion_rejects_wrong_secrets_and_other_principals(tmp_path: Path) -> None:
    credential = Submitters(tmp_path).issue("phone")
    client = TestClient(create_intake_app(tmp_path))
    for token in ("", credential.token + "wrong", "weedzrev_1_wrong"):
        assert (
            client.delete("/submitter", headers={"Authorization": f"Bearer {token}"}).status_code
            == 401
        )
    assert Submitters(tmp_path).submitter(credential.token) == credential.id


def test_operator_can_delete_all_data_for_a_lost_revoked_device(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    from weedz.intake.cli import main

    credential = Submitters(tmp_path).issue("lost phone")
    client = TestClient(create_intake_app(tmp_path))
    headers = {"Authorization": f"Bearer {credential.token}"}
    assert (
        client.put(f"/reports/{new_id()}", json=with_image(jpeg()), headers=headers).status_code
        == 201
    )
    Submitters(tmp_path).revoke(credential.id)
    command = ["delete-submitter", "--id", str(credential.id), "--intake-dir", str(tmp_path)]
    main(command)
    main(command)
    assert "Deleted" in capsys.readouterr().out
    assert not ReportStore(tmp_path).active()
    with pytest.raises(SystemExit, match="No submitter"):
        main(["delete-submitter", "--id", "999", "--intake-dir", str(tmp_path)])


def test_deletion_finishes_while_an_authenticated_upload_is_decoding(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import threading
    from concurrent.futures import ThreadPoolExecutor

    decoding, resume = threading.Event(), threading.Event()
    credential = Submitters(tmp_path).issue("phone")
    headers = {"Authorization": f"Bearer {credential.token}"}

    def paused(data: bytes, max_pixels: int) -> bytes:
        decoding.set()
        assert resume.wait(5)
        return data

    monkeypatch.setattr("weedz.intake.api.clean_image", paused)
    with TestClient(create_intake_app(tmp_path)) as client, ThreadPoolExecutor(1) as pool:
        upload = pool.submit(
            client.put, f"/reports/{new_id()}", json=with_image(jpeg()), headers=headers
        )
        try:
            assert decoding.wait(5)
            assert client.delete("/submitter", headers=headers).status_code == 200
        finally:
            resume.set()
        assert upload.result().status_code == 410
    assert not ReportStore(tmp_path).active()
    assert not list((tmp_path / "reports/images").iterdir())


def test_another_process_cannot_store_after_the_deletion_barrier(tmp_path: Path) -> None:
    import subprocess
    import sys

    credential = Submitters(tmp_path).issue("phone")
    Deletions(tmp_path).begin(credential.id)
    script = """
import json, sys
from pathlib import Path
from weedz.intake.store import ReportStore, Withdrawn
from weedz.intake.schema import Report
from weedz.intake.limits import Limits
store = ReportStore(Path(sys.argv[1]))
try:
    store.receive(int(sys.argv[2]), sys.argv[3], Report.model_validate_json(sys.stdin.read()),
                  "digest", None, Limits())
except Withdrawn:
    sys.exit(0)
sys.exit(1)
"""
    result = subprocess.run(
        [sys.executable, "-c", script, str(tmp_path), str(credential.id), new_id()],
        input=json.dumps(report()),
        text=True,
        capture_output=True,
        timeout=10,
    )
    assert result.returncode == 0, result.stderr
    assert not ReportStore(tmp_path).active()


def test_bulk_erasure_preserves_existing_withdrawal_times(tmp_path: Path) -> None:
    credential = Submitters(tmp_path).issue("phone")
    client = TestClient(create_intake_app(tmp_path))
    headers = {"Authorization": f"Bearer {credential.token}"}
    report_id = new_id()
    assert client.put(f"/reports/{report_id}", json=report(), headers=headers).status_code == 201
    withdrawn = client.delete(f"/reports/{report_id}", headers=headers).json()
    assert client.delete("/submitter", headers=headers).status_code == 200
    receipt = ReportStore(tmp_path).receipt(credential.id, report_id)
    assert receipt is not None
    assert receipt.withdrawn_at == withdrawn["withdrawn_at"]
    assert receipt.received_at == withdrawn["received_at"]


def test_deletion_marker_waits_for_specialist_read_materialization(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import threading
    from concurrent.futures import ThreadPoolExecutor

    from weedz.intake.schema import ReportContent

    parsing, resume = threading.Event(), threading.Event()
    original = ReportContent.model_validate_json
    credential = Submitters(tmp_path).issue("phone")
    client = TestClient(create_intake_app(tmp_path))
    headers = {"Authorization": f"Bearer {credential.token}"}
    assert client.put(f"/reports/{new_id()}", json=report(), headers=headers).status_code == 201

    def paused(body: str, **options: object) -> ReportContent:
        parsing.set()
        assert resume.wait(5)
        return original(body, **options)  # type: ignore[arg-type]

    monkeypatch.setattr(ReportContent, "model_validate_json", paused)
    with ThreadPoolExecutor(2) as pool:
        reading = pool.submit(ReportStore(tmp_path).active)
        try:
            assert parsing.wait(5)
            erasing = pool.submit(Deletions(tmp_path).delete, credential.id)
            # A marker writer cannot commit while the read still materializes bodies.
            from concurrent.futures import TimeoutError as FutureTimeout

            with pytest.raises(FutureTimeout):
                erasing.result(timeout=0.1)
        finally:
            resume.set()
        assert len(reading.result()) == 1
        assert erasing.result().status == "deleted"
    assert not ReportStore(tmp_path).active()


def test_late_withdrawal_cannot_create_state_after_bulk_erasure(tmp_path: Path) -> None:
    credential = Submitters(tmp_path).issue("phone")
    Deletions(tmp_path).delete(credential.id)
    # Represents an independently authenticated DELETE resumed after bulk completion.
    with pytest.raises(Withdrawn):
        ReportStore(tmp_path).withdraw(
            credential.id, new_id(), before_arrival=True, limits=Limits()
        )
    with sqlite3.connect(tmp_path / "reports/reports.sqlite3") as db:
        assert db.execute("SELECT COUNT(*) FROM reports").fetchone() == (0,)
        assert db.execute("SELECT COUNT(*) FROM usage").fetchone() == (0,)


def test_operator_withdrawal_reports_an_existing_bulk_deletion(tmp_path: Path) -> None:
    from weedz.intake.cli import main

    credential = Submitters(tmp_path).issue("phone")
    Deletions(tmp_path).delete(credential.id)
    with pytest.raises(SystemExit, match="already requested deletion"):
        main(
            [
                "withdraw",
                "--submitter",
                str(credential.id),
                "--report",
                new_id(),
                "--not-yet-received",
                "--intake-dir",
                str(tmp_path),
            ]
        )


def test_operator_deletion_sweeps_crops_left_by_an_abrupt_upload_exit(tmp_path: Path) -> None:
    import subprocess
    import sys

    credential = Submitters(tmp_path).issue("phone")
    other = Submitters(tmp_path).issue("other phone")
    client = TestClient(create_intake_app(tmp_path))
    headers = {"Authorization": f"Bearer {other.token}"}
    assert (
        client.put(f"/reports/{new_id()}", json=with_image(jpeg()), headers=headers).status_code
        == 201
    )
    script = """
import os, sys
from pathlib import Path
from weedz.intake.store import ReportStore
store = ReportStore(Path(sys.argv[1]))
with store._transaction():
    store._write_image(sys.stdin.buffer.read())
    os._exit(23)  # SQLite rolls back; durable image has no committed report owner.
"""
    result = subprocess.run(
        [sys.executable, "-c", script, str(tmp_path)], input=jpeg(), capture_output=True, timeout=10
    )
    assert result.returncode == 23, result.stderr
    assert len(list((tmp_path / "reports/images").iterdir())) == 2
    # No API startup sweep between the crash and this operator-side erasure.
    Deletions(tmp_path).delete(credential.id)
    assert len(list((tmp_path / "reports/images").iterdir())) == 1
    assert [item.submitter for item in ReportStore(tmp_path).active()] == [other.id]
