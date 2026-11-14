"""Retry-safe side effects with only small records returned to Temporal history."""

import hashlib
import json
import platform
from importlib.metadata import version
from pathlib import Path
from typing import Any

from temporalio import activity

from weedz.discovery.effort import summarize_effort
from weedz.discovery.records import RunSpec
from weedz.discovery.source import Inaturalist
from weedz.discovery.store import Store


class Activities:
    def __init__(self, root: Path) -> None:
        self.store = Store(root)
        self.screener: Any = None

    @activity.defn
    def collect_photos(self, payload: dict) -> dict:
        run_id = payload["run_id"]
        spec = RunSpec.model_validate(payload["spec"])
        self.store.create_run(run_id, spec)
        self.store.status(run_id, "acquiring", "Fetching attributed regional photos")
        activity.heartbeat("acquiring")
        source = Inaturalist(self.store.root)
        try:
            photos = source.collect(run_id, spec, progress=activity.heartbeat)
        finally:
            source.close()
        self.store.save_photos(run_id, photos)
        if not photos:
            raise ValueError("No eligible photos returned for the bounded regional query")
        return {"count": len(photos)}

    @activity.defn
    def screen_photos(self, payload: dict) -> dict:
        from weedz.discovery.inference import Screener

        run_id = payload["run_id"]
        self.store.status(run_id, "screening", "Loading pinned BioCLIP model on CPU")
        activity.heartbeat("loading model")
        if self.screener is None:
            self.screener = Screener()
        previous = next(run["model"] for run in self.store.runs() if run["id"] == run_id)
        if previous and previous != self.screener.metadata:
            raise ValueError(
                "Scoring configuration changed; start a new run to preserve provenance"
            )
        self.store.model(run_id, self.screener.metadata)
        photos = self.store.photos(run_id)
        for index, photo in enumerate(photos):
            activity.heartbeat(f"{index}/{len(photos)}")
            path = self.store.root / photo["image_path"]
            if hashlib.sha256(path.read_bytes()).hexdigest() != photo["sha256"]:
                raise ValueError(f"Image checksum mismatch: {photo['id']}")
            if not photo["scores"]:
                self.store.score(run_id, photo["id"], self.screener.screen(path))
            self.store.status(run_id, "screening", f"Scored {index + 1} of {len(photos)} photos")
        return {"count": len(photos)}

    @activity.defn
    def export_run(self, payload: dict) -> dict:
        run_id = payload["run_id"]
        activity.heartbeat("exporting")
        self.store.status(run_id, "exporting", "Writing the screening manifest")
        result = export(self.store, run_id)
        result["run"]["status"] = "completed"
        result["run"]["detail"] = "Screening complete; expert review is pending"
        destination = self.store.root / "runs" / run_id / "manifest.json"
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary = destination.with_suffix(".tmp")
        temporary.write_text(json.dumps(result, indent=2))
        temporary.replace(destination)
        self.store.status(run_id, "completed", "Screening complete; expert review is pending")
        return {"manifest": str(destination), "count": len(result["photos"])}

    @activity.defn
    def fail_run(self, payload: dict) -> None:
        self.store.status(payload["run_id"], "failed", payload["error"])


def export(store: Store, run_id: str) -> dict:
    run = next((item for item in store.runs() if item["id"] == run_id), None)
    if run is None:
        raise KeyError(run_id)
    snapshots = store.root / "runs" / run_id
    photos = store.photos(run_id)
    history = [
        dict(photo_id=photo["id"], events=store.reviews(run_id, photo["id"])) for photo in photos
    ]
    return {
        "schema": 1,
        "run": run,
        "photos": photos,
        "review_history": history,
        "review_effort": summarize_effort(photos, history),
        "source_snapshots": {
            path.name: hashlib.sha256(path.read_bytes()).hexdigest()
            for path in snapshots.glob("*.json")
            if path.name != "manifest.json"
        },
        "software": {
            "python": platform.python_version(),
            **{name: version(name) for name in ["weedz", "torch", "open-clip-torch", "temporalio"]},
        },
        "limitations": [
            "Uncalibrated image/text similarity, not verified detections or probabilities",
            "Windows are search regions, not plant boundaries; no segmentation model used",
            "Reference photos are separate; animal photos have no background weed ground truth",
            "Observation coordinates locate the observation, not a confirmed weed",
            "No novelty comparison, infestation area estimate or external publication performed",
        ],
    }
