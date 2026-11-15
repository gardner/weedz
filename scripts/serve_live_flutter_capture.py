"""Run the actual Flutter web app and real isolated intake over loopback HTTPS.

No fake transport or app state is injected. Temporary credentials/certificates/database
are private to this process and are removed after capture. Never uses live intake data.
"""

import argparse
import base64
import json
import os
import sqlite3
import subprocess
from pathlib import Path
from typing import Any

import uvicorn
from starlette.staticfiles import StaticFiles

from weedz.intake.api import create_intake_app
from weedz.intake.submitters import Submitters


def source_report(pilot: Path, image: Path) -> dict[str, Any]:
    with sqlite3.connect(f"file:{pilot / 'discovery.sqlite3'}?mode=ro", uri=True) as source:
        row = source.execute(
            "SELECT record,scores FROM photos WHERE run_id=? AND id=?",
            ("nelson-tasman-3e62ad801459", "inat-250240131-447484684"),
        ).fetchone()
        record, scores = json.loads(row[0]), json.loads(row[1])
        stamp = json.loads(
            source.execute(
                "SELECT model FROM runs WHERE id=?", ("nelson-tasman-3e62ad801459",)
            ).fetchone()[0]
        )
    if record["photo_license"] != "cc-by":
        raise ValueError("Only the attributed public CC BY source is allowed")
    return {
        "schema_version": 1,
        "app_version": "0.1.0+capture",
        "candidate": {"taxon": scores["best_species"], "score": scores["margin"]},
        "model": {
            "model_key": "bioclip",
            "revision": stamp["revision"],
            "ranking_revision": stamp["ranking_revision"],
        },
        "consent": {
            "wording_version": "2026-11",
            "image": True,
            "location": False,
            "licence": "cc-by",
            "credit": "Saryu Mae 前 朝琉",
            "uses": ["review"],
        },
        "image": base64.b64encode(image.read_bytes()).decode(),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--web-build", type=Path, required=True)
    parser.add_argument("--source-pilot", type=Path, required=True)
    parser.add_argument("--public-image", type=Path, required=True)
    parser.add_argument("--private-state", type=Path, required=True)
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
                "report": source_report(args.source_pilot, args.public_image),
            }
        )
    )
    os.chmod(credential_file, 0o600)
    app = create_intake_app(intake)
    app.mount("/", StaticFiles(directory=args.web_build.resolve(), html=True))
    uvicorn.run(app, host="127.0.0.1", port=8443, ssl_keyfile=str(key), ssl_certfile=str(cert))


if __name__ == "__main__":
    main()
