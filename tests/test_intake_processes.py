"""Exercise intake ordering with an actual independent server process (#97)."""

import multiprocessing
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from intake_helpers import jpeg, new_id, with_image
from test_intake_concurrency import token

from weedz.intake.api import create_intake_app
from weedz.intake.cli import main
from weedz.intake.limits import Limits
from weedz.intake.store import ReportStore


def upload(root: Path, secret: str, report_id: str) -> None:
    import weedz.intake.api as api

    clean = api.clean_image

    def slow(data: bytes, max_pixels: int) -> bytes:
        (root / "decoding").touch()
        deadline = time.monotonic() + 10
        while not (root / "release").exists():
            if time.monotonic() > deadline:
                raise TimeoutError("Test did not release decoding")
            time.sleep(0.01)
        return clean(data, max_pixels)

    api.clean_image = slow
    client = TestClient(create_intake_app(root, Limits(reports_per_day=1)))
    response = client.put(
        f"/reports/{report_id}",
        json=with_image(jpeg()),
        headers={"Authorization": f"Bearer {secret}"},
    )
    (root / "result").write_text(str(response.status_code))


@pytest.mark.parametrize("operation", ["upload", "operator-withdraw"])
def test_api_and_operator_share_the_other_process_turn(tmp_path: Path, operation: str) -> None:
    secret, report_id = token(tmp_path), new_id()
    # Create the second app first: startup maintenance is covered separately.
    client = TestClient(create_intake_app(tmp_path, Limits(reports_per_day=1)))
    worker = multiprocessing.get_context("spawn").Process(
        target=upload, args=(tmp_path, secret, report_id)
    )
    worker.start()
    try:
        deadline = time.monotonic() + 5
        while not (tmp_path / "decoding").exists():
            assert time.monotonic() < deadline and worker.is_alive()
            time.sleep(0.01)
        with ThreadPoolExecutor(1) as pool:
            if operation == "upload":
                pending = pool.submit(
                    client.put,
                    f"/reports/{new_id()}",
                    json=with_image(jpeg()),
                    headers={"Authorization": f"Bearer {secret}"},
                )
            else:
                pending = pool.submit(
                    main,
                    [
                        "withdraw",
                        "--submitter",
                        "1",
                        "--report",
                        report_id,
                        "--intake-dir",
                        str(tmp_path),
                    ],
                )
            try:
                time.sleep(0.1)
                assert not pending.done(), "Must wait through the other process's decoding"
            finally:
                (tmp_path / "release").touch()
            result = pending.result(timeout=5)
        worker.join(5)
        assert worker.exitcode == 0
        assert (tmp_path / "result").read_text() == "201"
        if operation == "upload":
            assert result is not None
            assert result.status_code == 429
        else:
            assert ReportStore(tmp_path).active() == []
    finally:
        (tmp_path / "release").touch()
        if worker.is_alive():
            worker.terminate()
        worker.join(5)
