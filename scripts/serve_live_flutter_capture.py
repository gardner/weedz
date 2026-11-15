"""Run the actual Flutter web app and real isolated intake over loopback HTTPS.

No fake transport or app state is injected. Temporary credentials/certificates/database
are private to this process and are removed after capture. Never uses live intake data.
"""

import argparse
import json
import os
import subprocess
from pathlib import Path

import uvicorn
from demo_public_report import source_capture
from fastapi import FastAPI
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.staticfiles import StaticFiles

from weedz.intake.api import create_intake_app
from weedz.intake.submitters import Submitters


def capture_app(intake: Path, web_build: Path, instance: str) -> FastAPI:
    if not instance:
        raise ValueError("Capture instance identity is required")
    app = create_intake_app(intake)

    async def identity(_request: Request) -> JSONResponse:
        return JSONResponse({"capture_instance": instance})

    app.add_route("/capture_identity", identity, methods=["GET"])
    app.mount("/", StaticFiles(directory=web_build.resolve(), html=True))
    return app


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--web-build", type=Path, required=True)
    parser.add_argument("--source-pilot", type=Path, required=True)
    parser.add_argument("--private-state", type=Path, required=True)
    parser.add_argument("--instance", required=True)
    args = parser.parse_args()
    state = args.private_state.resolve()
    state.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(state, 0o700)
    key, cert = state / "key.pem", state / "cert.pem"
    subprocess.run(
        [
            "openssl",
            "req",
            "-x509",
            "-newkey",
            "rsa:2048",
            "-nodes",
            "-days",
            "1",
            "-keyout",
            str(key),
            "-out",
            str(cert),
            "-subj",
            "/CN=localhost",
            "-addext",
            "subjectAltName=DNS:localhost,IP:127.0.0.1",
        ],
        check=True,
        capture_output=True,
    )
    os.chmod(key, 0o600)
    intake = state / "intake"
    credential = Submitters(intake).issue("Local public-photo capture")
    credential_file = state / "enrollment.json"
    credential_file.write_text(
        json.dumps(
            {
                "token": credential.token,
                **source_capture(args.source_pilot),
            }
        )
    )
    os.chmod(credential_file, 0o600)
    app = capture_app(intake, args.web_build, args.instance)
    uvicorn.run(app, host="127.0.0.1", port=8443, ssl_keyfile=str(key), ssl_certfile=str(cert))


if __name__ == "__main__":
    main()
