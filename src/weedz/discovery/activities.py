"""Retry-safe side effects with only small records returned to Temporal history."""

import contextvars
import hashlib
import json
import platform
import threading
from collections.abc import Callable
from importlib.metadata import version
from pathlib import Path
from typing import Any

from temporalio import activity

from weedz.discovery.audit import audit_sample, summarize_audit
from weedz.discovery.effort import summarize_effort
from weedz.discovery.encounters import encounter_groups, summarize, with_encounters
from weedz.discovery.lookalikes import summarize_lookalikes
from weedz.discovery.occurrences import with_references
from weedz.discovery.records import Photo, RunSpec
from weedz.discovery.sampling import coverage
from weedz.discovery.source import Inaturalist
from weedz.discovery.store import Store


def while_heartbeating[T](work: Callable[[], T], detail: str, every: float = 20.0) -> T:
    """Run blocking work (e.g. a first 1.7 GB model download) while heartbeating, so the
    activity's two-minute heartbeat timeout measures liveness, not download speed."""
    context = contextvars.copy_context()
    done = threading.Event()

    def beat() -> None:
        while not done.wait(every):
            context.run(activity.heartbeat, detail)

    thread = threading.Thread(target=beat, daemon=True)
    activity.heartbeat(detail)
    thread.start()
    try:
        return work()
    finally:
        done.set()
        thread.join()


class Activities:
    def __init__(self, root: Path) -> None:
        self.store = Store(root)
        self.screeners: dict[str, Any] = {}

    @activity.defn
    def collect_photos(self, payload: dict) -> dict:
        run_id = payload["run_id"]
        spec = RunSpec.from_saved(payload["spec"])
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
        from weedz.discovery.inference import Screener, subject_label

        run_id = payload["run_id"]
        self.store.status(run_id, "screening", "Loading pinned BioCLIP model on CPU")
        activity.heartbeat("loading model")
        run = next(item for item in self.store.runs() if item["id"] == run_id)
        key = RunSpec.from_saved(run["spec"]).model
        if key not in self.screeners:
            # Keep only the active model: two encoders (0.6 + 1.7 GB) could exhaust memory.
            self.screeners.clear()
            self.screeners[key] = while_heartbeating(
                lambda: Screener.load(self.store.root / "embeddings", model=key),
                f"loading {key} model",
            )
        screener = self.screeners[key]
        # Metadata saved before model choice existed was always the original BioCLIP.
        previous = run["model"] and {"model_key": "bioclip"} | run["model"]
        if previous and previous != screener.metadata:
            raise ValueError(
                "Scoring configuration changed; start a new run to preserve provenance"
            )
        self.store.model(run_id, screener.metadata)
        photos = self.store.photos(run_id)
        for index, photo in enumerate(photos):
            activity.heartbeat(f"{index}/{len(photos)}")
            path = self.store.root / photo["image_path"]
            if hashlib.sha256(path.read_bytes()).hexdigest() != photo["sha256"]:
                raise ValueError(f"Image checksum mismatch: {photo['id']}")
            if not photo["scores"]:
                self.store.score(run_id, photo["id"], screener.screen(path, subject_label(photo)))
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


def review_history(store: Store, run_id: str, photos: list[dict]) -> list[dict]:
    return [
        dict(photo_id=photo["id"], events=store.reviews(run_id, photo["id"])) for photo in photos
    ]


def export(store: Store, run_id: str) -> dict:
    run = next((item for item in store.runs() if item["id"] == run_id), None)
    if run is None:
        raise KeyError(run_id)
    snapshots = store.root / "runs" / run_id
    references, photos = with_references(store.root, store.photos(run_id))
    history = review_history(store, run_id, photos)
    return {
        "schema": 1,
        "run": run,
        "photos": with_encounters(photos),
        "references": references,
        "encounters": summarize(photos, encounter_groups(photos)),
        "lookalikes": summarize_lookalikes(photos),
        "corpus_coverage": coverage(
            [Photo.model_validate(p) for p in photos if p["cohort"] == "incidental"],
            RunSpec.from_saved(run["spec"]).sampling,
        ),
        "review_history": history,
        "review_effort": summarize_effort(photos, history),
        "audit": summarize_audit(
            photos,
            audit_sample(run_id, photos),
            store.latest_audits(run_id),
            store.latest_audits(run_id, blind=False),
        ),
        "audit_history": [
            dict(photo_id=photo["id"], events=store.audits(run_id, photo["id"])) for photo in photos
        ],
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
            "Known-record comparison is distance and date only, not a novelty verdict; "
            "no infestation area estimate or external publication performed",
            "Site-visit groups link photos by observer, date and distance; not the same plant",
            (
                "Photos with obscured, missing or imprecise locations, unknown accuracy or no date "
                "are ungrouped, not counted as independent visits"
            ),
        ],
    }
