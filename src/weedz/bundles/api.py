"""Serve a published bundle tree (issue #59): its own app, never mounted on the review API.

Phones are not reviewers, and a bundle is public, signed data, so this needs no token.
In production the same tree can sit on any static host or CDN; this app is for
development and small deployments. The manifest is always revalidated, while artefacts,
named by their hash, are cached forever.
"""

import re
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse

from weedz.bundles.publish import MANIFEST, artefact_path

SHA256 = re.compile(r"^[0-9a-f]{64}$")


def create_app(out: Path) -> FastAPI:
    app = FastAPI(title="Weedz model bundles", version="1.0.0", openapi_url=None)

    @app.get(f"/bundles/{MANIFEST}")
    def manifest() -> FileResponse:
        path = out / MANIFEST
        if not path.exists():
            raise HTTPException(404, "No bundle has been published")
        return FileResponse(
            path, media_type="application/json", headers={"Cache-Control": "no-cache"}
        )

    @app.get("/bundles/artifacts/sha256/{digest}")
    def artefact(digest: str) -> FileResponse:
        # Checked before it touches a path, so no name can reach outside the tree.
        if not SHA256.fullmatch(digest) or not artefact_path(out, digest).is_file():
            raise HTTPException(404, "No such artefact")
        return FileResponse(
            artefact_path(out, digest),
            media_type="application/octet-stream",
            headers={"Cache-Control": "public, max-age=31536000, immutable"},
        )

    return app
