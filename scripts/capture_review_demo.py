"""Run isolated snapshot servers, record the actual web UI, then stop only our children."""

import argparse
import os
import signal
import subprocess
import time
from pathlib import Path
from urllib.request import urlopen

from demo_paths import outside_git


def ready(url: str) -> None:
    deadline = time.monotonic() + 40
    while time.monotonic() < deadline:
        try:
            with urlopen(url, timeout=2) as response:
                if response.status == 200:
                    return
        except OSError:
            time.sleep(0.2)
    raise TimeoutError(f"Local capture server did not become ready: {url}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    output = outside_git(args.output)
    output.mkdir(parents=True, exist_ok=True)
    environment = os.environ | {
        "WEEDZ_API_URL": "http://127.0.0.1:8312",
        "WEEDZ_WEB_URL": "http://127.0.0.1:3012",
        "WEEDZ_CAPTURE_DIR": str(output),
    }
    processes: list[subprocess.Popen[bytes]] = []
    try:
        with (output / "api.log").open("w") as api_log, (output / "web.log").open("w") as web_log:
            processes.append(
                subprocess.Popen(
                    [
                        "uv",
                        "run",
                        "python",
                        "scripts/serve_demo_snapshot.py",
                        "--snapshot",
                        str(args.snapshot),
                    ],
                    cwd=root,
                    env=environment,
                    stdout=api_log,
                    stderr=subprocess.STDOUT,
                    start_new_session=True,
                )
            )
            ready("http://127.0.0.1:8312/runs")
            processes.append(
                subprocess.Popen(
                    [
                        "pnpm",
                        "--dir",
                        "web",
                        "exec",
                        "next",
                        "start",
                        "--hostname",
                        "127.0.0.1",
                        "--port",
                        "3012",
                    ],
                    cwd=root,
                    env=environment,
                    stdout=web_log,
                    stderr=subprocess.STDOUT,
                    start_new_session=True,
                )
            )
            ready("http://127.0.0.1:3012")
            subprocess.run(
                ["pnpm", "--dir", "web", "exec", "node", "scripts/capture-demo.mjs"],
                cwd=root,
                env=environment,
                check=True,
            )
    finally:
        for process in reversed(processes):
            if process.poll() is None:
                os.killpg(process.pid, signal.SIGTERM)
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait()


if __name__ == "__main__":
    main()
