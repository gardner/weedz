"""Capture the actual app against a real temporary intake, then erase private runtime state."""

import argparse
import json
import os
import signal
import sqlite3
import ssl
import subprocess
import tempfile
import time
from pathlib import Path
from urllib.request import urlopen

from demo_paths import outside_git


def verify_erasure(state: Path) -> tuple[int, int]:
    with sqlite3.connect(state / "intake/reports/reports.sqlite3") as db:
        active = db.execute("SELECT COUNT(*) FROM reports WHERE body IS NOT NULL").fetchone()[0]
    crops = sum(path.is_file() for path in (state / "intake/reports/images").rglob("*"))
    if active or crops:
        raise RuntimeError(
            f"Erasure verification failed: {active} report bodies and {crops} crop files remain"
        )
    return active, crops


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--source-pilot", type=Path, required=True)
    parser.add_argument("--ffmpeg", type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    output = outside_git(args.output)
    source = args.source_pilot.resolve()
    if output.is_relative_to(source) or source.is_relative_to(output):
        raise ValueError("Capture output and source pilot must be independent directories")
    output.mkdir(parents=True, exist_ok=False)
    with tempfile.TemporaryDirectory(prefix="weedz-live-capture-") as private:
        state = Path(private)
        command = [
            "uv",
            "run",
            "python",
            "scripts/serve_live_flutter_capture.py",
            "--web-build",
            str(root / "mobile/build/web"),
            "--source-pilot",
            str(args.source_pilot),
            "--private-state",
            str(state),
        ]
        with (output / "server.log").open("w") as log:
            server = subprocess.Popen(
                command, cwd=root, stdout=log, stderr=subprocess.STDOUT, start_new_session=True
            )
            try:
                deadline = time.monotonic() + 30
                while time.monotonic() < deadline:
                    try:
                        with urlopen(
                            "https://127.0.0.1:8443",
                            context=ssl._create_unverified_context(),
                            timeout=2,
                        ):
                            break
                    except OSError:
                        time.sleep(0.2)
                else:
                    raise TimeoutError("Isolated HTTPS intake did not become ready")
                environment = os.environ | {
                    "WEEDZ_PRIVATE_STATE": private,
                    "WEEDZ_CAPTURE_DIR": str(output),
                    "WEEDZ_FFMPEG": str(args.ffmpeg),
                }
                subprocess.run(
                    ["pnpm", "--dir", "web", "exec", "node", "scripts/capture-live-flutter.mjs"],
                    cwd=root,
                    env=environment,
                    check=True,
                )
                active, crops = verify_erasure(state)
                (output / "erasure-verification.json").write_text(
                    json.dumps(
                        {
                            "active_report_bodies_after_real_app_deletion": active,
                            "remaining_crop_files": crops,
                            "private_runtime_state": (
                                "Temporary certificate, credential and isolated intake "
                                "removed after capture"
                            ),
                            "live_private_intake_touched": False,
                        },
                        indent=2,
                    )
                    + "\n"
                )
            finally:
                if server.poll() is None:
                    os.killpg(server.pid, signal.SIGTERM)
                    server.wait(timeout=10)


if __name__ == "__main__":
    main()
