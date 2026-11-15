"""Run isolated snapshot servers, record the actual web UI, then stop only our children."""

import argparse
import json
import os
import signal
import socket
import ssl
import subprocess
import time
import uuid
from pathlib import Path
from urllib.request import urlopen

from demo_paths import new_output


def available_port() -> int:
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        return int(listener.getsockname()[1])


def ready(
    url: str,
    child: subprocess.Popen[bytes],
    instance: str,
    *,
    context: ssl.SSLContext | None = None,
) -> None:
    deadline = time.monotonic() + 40
    while time.monotonic() < deadline:
        if child.poll() is not None:
            raise RuntimeError(f"Owned capture server exited before readiness: {url}")
        try:
            with urlopen(url, timeout=2, context=context) as response:
                if response.status == 200:
                    if json.loads(response.read()) != {"capture_instance": instance}:
                        raise ValueError(f"Listener belongs to another capture instance: {url}")
                    if child.poll() is not None:
                        raise RuntimeError(f"Owned capture server exited during readiness: {url}")
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
    output = new_output(args.output)
    snapshot = args.snapshot.resolve()
    if output.is_relative_to(snapshot) or snapshot.is_relative_to(output):
        raise ValueError("Capture output and source snapshot must be independent directories")
    output.mkdir(parents=True, exist_ok=False)
    api_port, web_port = available_port(), available_port()
    while web_port == api_port:
        web_port = available_port()
    instance = uuid.uuid4().hex
    api_origin = f"http://127.0.0.1:{api_port}"
    web_origin = f"http://127.0.0.1:{web_port}"
    environment = os.environ | {
        "WEEDZ_API_URL": api_origin,
        "WEEDZ_WEB_URL": web_origin,
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
                        str(snapshot),
                        "--port",
                        str(api_port),
                        "--instance",
                        instance,
                    ],
                    cwd=root,
                    env=environment,
                    stdout=api_log,
                    stderr=subprocess.STDOUT,
                    start_new_session=True,
                )
            )
            ready(f"{api_origin}/runs/capture_identity", processes[-1], instance)
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
                        str(web_port),
                    ],
                    cwd=root,
                    env=environment,
                    stdout=web_log,
                    stderr=subprocess.STDOUT,
                    start_new_session=True,
                )
            )
            ready(f"{web_origin}/api/runs/capture_identity", processes[-1], instance)
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
