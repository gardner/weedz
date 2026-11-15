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
from weedz.discovery.leads import selections
from weedz.discovery.limits import CAMERA_TO_PLANT_ALLOWANCE_M, with_limits
from weedz.discovery.lookalikes import summarize_lookalikes
from weedz.discovery.occurrences import with_references
from weedz.discovery.records import Photo, RunSpec
from weedz.discovery.sampling import coverage
from weedz.discovery.score_meaning import pin_meaning, score_meaning
from weedz.discovery.sharing import withdrawn
from weedz.discovery.source import Inaturalist, admitted_licences
from weedz.discovery.store import Store
from weedz.discovery.study_store import run_study
from weedz.discovery.suitability import suitability


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
    def __init__(self, root: Path, *, allowed_photo_licences: frozenset[str] | None = None) -> None:
        self.store = Store(root)
        self.allowed_photo_licences = admitted_licences(allowed_photo_licences)
        self.screeners: dict[str, Any] = {}
        self.proposer: Any = None

    def registered_activities(self) -> list[Callable[..., Any]]:
        return [
            self.collect_photos,
            self.segment_photos_v1,
            self.screen_photos,
            self.score_region_views_v1,
            self.export_run,
            self.fail_run,
        ]

    def preflight_segmentation(self) -> dict:
        from weedz.segmentation.runtime import load_proposer

        if self.proposer is None:
            self.proposer = load_proposer(self.store.root)
        return self.proposer.metadata

    def _proposer(self) -> Any:
        while_heartbeating(self.preflight_segmentation, "loading pinned SAM2.1 model")
        return self.proposer

    def _stages(self) -> Any:
        from weedz.segmentation.stages import PipelineStages

        return PipelineStages(
            self.store,
            self._proposer,
            self._screener,
            activity.heartbeat,
            lambda: activity.info().attempt,
            while_heartbeating,
        )

    @activity.defn
    def segment_photos_v1(self, payload: dict) -> dict:
        return self._stages().segment(payload["run_id"])

    @activity.defn
    def score_region_views_v1(self, payload: dict) -> dict:
        return self._stages().score_regions(payload["run_id"])

    @activity.defn
    def collect_photos(self, payload: dict) -> dict:
        run_id = payload["run_id"]
        spec = RunSpec.from_saved(payload["spec"])
        self.store.create_run(run_id, spec)
        self.store.status(run_id, "acquiring", "Fetching attributed regional photos")
        activity.heartbeat("acquiring")
        source = Inaturalist(self.store.root, allowed_photo_licences=self.allowed_photo_licences)
        try:
            photos = source.collect(run_id, spec, progress=activity.heartbeat)
        finally:
            source.close()
        if any(
            photo.photo_license not in self.allowed_photo_licences
            or photo.observation_license not in self.allowed_photo_licences
            for photo in photos
        ):
            raise ValueError("Collected photo violates the trusted source licence policy")
        self.store.save_photos(run_id, photos)
        if not photos:
            raise ValueError("No eligible photos returned for the bounded regional query")
        return {"count": len(photos)}

    def _screener(self, run_id: str) -> Any:
        from weedz.discovery.inference import Screener

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
        # Refuses a changed configuration; a resumed run keeps its pinned score meaning.
        self.store.model(run_id, pin_meaning(run["model"], screener.metadata))
        return screener

    @activity.defn
    def screen_photos(self, payload: dict) -> dict:
        from weedz.discovery.inference import subject_label

        run_id = payload["run_id"]
        screener = self._screener(run_id)
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
        if result.get("pipeline", {}).get("missing"):
            raise ValueError("Requested pipeline stages have not completed")
        detail = "Screening complete; expert review is pending"
        if result.get("pipeline", {}).get("outcome") == "partial":
            detail = (
                "Baseline screening complete; segmentation/region failures retained as "
                "explicit fallback; expert review pending"
            )
        result["run"]["status"] = "completed"
        result["run"]["detail"] = detail
        # Summarised again, so it reads the run as completed rather than still exporting.
        result["source_suitability"] = suitability(result)
        destination = self.store.root / "runs" / run_id / "manifest.json"
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary = destination.with_suffix(".tmp")
        temporary.write_text(json.dumps(result, indent=2))
        temporary.replace(destination)
        self.store.status(run_id, "completed", detail)
        completion = {"manifest": str(destination), "count": len(result["photos"])}
        if "pipeline" in result:
            completion["pipeline_outcome"] = result["pipeline"]["outcome"]
        return completion

    @activity.defn
    def fail_run(self, payload: dict) -> None:
        self.store.status(payload["run_id"], "failed", payload["error"])


def review_history(store: Store, run_id: str, photos: list[dict]) -> list[dict]:
    return [
        dict(
            photo_id=photo["id"],
            events=store.reviews(run_id, photo["id"]),
            judgements=store.judgements(run_id, photo["id"]),
            referrals=photo.get("referrals", []),
        )
        for photo in photos
    ]


def export(store: Store, run_id: str) -> dict:
    run = next((item for item in store.runs() if item["id"] == run_id), None)
    if run is None:
        raise KeyError(run_id)
    snapshots = store.root / "runs" / run_id
    # A withdrawn report is used for nothing further, so nothing is derived from it (#60).
    every = store.photos(run_id)
    live = [photo for photo in every if not withdrawn(photo)]
    references, photos = with_references(store.root, live)
    kept = {photo["id"] for photo in photos}
    history = review_history(store, run_id, photos)
    result = {
        "schema": 1,
        "run": run,
        "photos": with_limits(with_encounters(photos)),
        "references": references,
        "encounters": summarize(photos, encounter_groups(photos)),
        "lookalikes": summarize_lookalikes(photos),
        # What the run's scores mean, for its model and ranking revision (#16).
        "score_meaning": score_meaning(run["model"]),
        "corpus_coverage": coverage(
            [Photo.model_validate(p) for p in photos if p["cohort"] == "incidental"],
            # The device-report run made no query, so it has no sampling (#58).
            RunSpec.from_saved(run["spec"]).sampling if run["spec"] else None,
        ),
        "review_history": history,
        "review_effort": summarize_effort(photos, history),
        "audit": summarize_audit(
            photos,
            # Drawn from every photo, as the review app draws it, less the withdrawn.
            audit_sample(run_id, every) & kept,
            store.latest_audits(run_id),
            store.latest_audits(run_id, blind=False),
        ),
        "lead_selections": [
            event for event in selections(store, run_id) if event["photo_id"] in kept
        ],
        # The study this run serves, at its latest version (PRD P01).
        "study": run_study(store, run_id),
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
            (
                "Finding boxes are reviewer-drawn visible extents, not segmentation; other "
                "taxa are verbatim reviewer text, not matched to a taxonomy"
            ),
            "Reference photos are separate; animal photos have no background weed ground truth",
            "Observation coordinates locate the observation, not a confirmed weed",
            (
                "Each photo's search area is centred on the observation point, never a "
                "plant point, with a radius of reported accuracy plus a declared "
                f"{CAMERA_TO_PLANT_ALLOWANCE_M:g} m camera-to-plant allowance; obscured, "
                "missing or unknown-accuracy locations have none. If a plant is visible, "
                "the photo dates it to when it was photographed, not to now"
            ),
            "Known-record comparison is distance and date only, not a novelty verdict; "
            "no infestation area estimate or external publication performed",
            "Site-visit groups link photos by observer, date and distance; not the same plant",
            (
                "Judgements of identity, location, history and novelty are attributed reviewer "
                "opinions, kept per dimension; no judgement means unassessed, and only a "
                "noted 'verified_new_locality' claims a new locality"
            ),
            (
                "Referrals ask for specialist assessment with a reason; an answer is the "
                "named specialist's note, not a verified identification, and never changes "
                "a reviewer's decision or judgement. Names are attribution, not identity"
            ),
            (
                "Leads selected for follow-up are attributed team choices with a reason, "
                "not verified findings; the follow-up package carries only those selected"
            ),
            (
                "Photos with obscured, missing or imprecise locations, unknown accuracy or no date "
                "are ungrouped, not counted as independent visits"
            ),
        ],
    }
    from weedz.segmentation.summary import pipeline_summary

    pipeline = pipeline_summary(store, run_id)
    if pipeline is not None:
        result["pipeline"] = pipeline
        result["limitations"][1] = (
            "Baseline windows remain search regions, not plant boundaries; separate class-agnostic "
            "SAM2.1 masks may miss plants or include other objects, and neither mask quality "
            "nor proposal-view ranking is identification confidence"
        )
    # What the collection can and cannot support, from the parts above (PRD P02, P14).
    return result | {"source_suitability": suitability(result)}
