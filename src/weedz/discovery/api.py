"""Local review API. Bind to loopback; Next.js proxies requests on the same origin."""

import uuid
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from temporalio.client import Client

from weedz.discovery.activities import export
from weedz.discovery.occurrences import with_references
from weedz.discovery.records import TASK_QUEUE, Review, RunSpec
from weedz.discovery.store import Store
from weedz.discovery.workflows import DiscoveryWorkflow


class ReviewAPI:
    def __init__(self, root: Path, temporal_address: str) -> None:
        self.store = Store(root)
        self.temporal_address = temporal_address

    def run(self, run_id: str) -> dict:
        result = next((item for item in self.store.runs() if item["id"] == run_id), None)
        if result is None:
            raise HTTPException(404, "Run not found")
        return result

    def runs(self) -> list[dict]:
        return self.store.runs()

    async def start(self, spec: RunSpec) -> dict:
        run_id = f"nelson-tasman-{uuid.uuid4().hex[:12]}"
        # Queue the workflow before exposing a queued run. Workers also ensure the
        # row exists, covering an API crash immediately after Temporal accepts it.
        try:
            client = await Client.connect(self.temporal_address)
            await client.start_workflow(
                DiscoveryWorkflow.run,
                spec.model_dump(mode="json"),
                id=run_id,
                task_queue=TASK_QUEUE,
            )
        except Exception as error:
            raise HTTPException(503, "Temporal is unavailable; start the local stack") from error
        self.store.create_run(run_id, spec)
        return {"id": run_id}

    def detail(self, run_id: str) -> dict:
        run = self.run(run_id)
        references, photos = with_references(self.store.root, self.store.photos(run_id))
        return {"run": run, "photos": photos, "references": references}

    def download(self, run_id: str) -> JSONResponse:
        self.run(run_id)
        return JSONResponse(
            export(self.store, run_id),
            headers={
                "Content-Disposition": f'attachment; filename="{run_id}.json"',
            },
        )

    def image(self, run_id: str, photo_id: str) -> FileResponse:
        photo = next((item for item in self.store.photos(run_id) if item["id"] == photo_id), None)
        if photo is None:
            raise HTTPException(404, "Photo not found")
        path = (self.store.root / photo["image_path"]).resolve()
        if not path.is_relative_to(self.store.root / "images") or not path.is_file():
            raise HTTPException(404, "Image not available")
        return FileResponse(path, media_type="image/jpeg")

    def review(self, run_id: str, photo_id: str, decision: Review) -> dict:
        try:
            self.store.review(run_id, photo_id, decision.status, decision.note)
        except KeyError as error:
            raise HTTPException(404, "Photo not found") from error
        return {"saved": True}


def create_app(root: Path, temporal_address: str = "localhost:7234") -> FastAPI:
    app = FastAPI(title="Weedz regional review", version="0.2.0")
    api = ReviewAPI(root, temporal_address)
    app.get("/runs")(api.runs)
    app.post("/runs", status_code=202)(api.start)
    app.get("/runs/{run_id}")(api.detail)
    app.get("/runs/{run_id}/export")(api.download)
    app.get("/runs/{run_id}/photos/{photo_id}/image")(api.image)
    app.post("/runs/{run_id}/photos/{photo_id}/review")(api.review)
    return app
