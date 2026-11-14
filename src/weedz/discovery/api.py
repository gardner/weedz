"""Local review API. Bind to loopback; Next.js proxies requests on the same origin."""

import uuid
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from temporalio.client import Client

from weedz.discovery.activities import export, review_history
from weedz.discovery.audit import audit_sample, summarize_audit
from weedz.discovery.effort import summarize_effort
from weedz.discovery.encounters import with_encounters
from weedz.discovery.judgements import Judgement, unsupported
from weedz.discovery.occurrences import with_references
from weedz.discovery.outcomes import outcomes
from weedz.discovery.records import SPECIES, TASK_QUEUE, Audit, Finding, Review, RunSpec
from weedz.discovery.referrals import Referral, ReferralEvent, uncitable
from weedz.discovery.store import Store
from weedz.discovery.workflows import DiscoveryWorkflow


def audit_state(photo_id: str, sample: set[str], *audits: dict[str, dict[str, str]]) -> dict:
    auditors = sorted({name for found in audits for name in found.get(photo_id, {})})
    return {"audit_sample": photo_id in sample, "audited": bool(auditors), "auditors": auditors}


def _names_suggestion(record: Finding, suggestion: str) -> bool:
    """Whether a correction repeats the suggestion, by key or by typed name."""
    if record.species is not None:
        return record.species == suggestion
    typed = (record.other_taxon or "").casefold()
    return typed in {suggestion.casefold(), SPECIES.get(suggestion, "").casefold()}


def check_finding(scores: dict, record: Finding) -> None:
    """A correction must differ from the suggestion; a box must fit the screened image."""
    suggestion: str = scores.get("best_species") or ""
    if record.kind == "correction" and not suggestion:
        raise HTTPException(409, "No suggestion to correct; record a missed plant instead")
    if record.kind == "correction" and _names_suggestion(record, suggestion):
        raise HTTPException(409, "That is the suggested species; use Species visible instead")
    if record.box is None:
        return
    if not (scores.get("width") and scores.get("height")):
        raise HTTPException(409, "Image size is unknown until screening; record without a box")
    if record.box[2] > scores["width"] or record.box[3] > scores["height"]:
        raise HTTPException(422, "The box extends beyond the image")


def check_target(photo: dict, record: Judgement) -> None:
    """A judgement is about the suggested species or one of this photo's recorded plants."""
    if record.finding_id is None and not photo["scores"].get("best_species"):
        raise HTTPException(409, "No suggestion to judge; judge a recorded plant instead")
    if record.finding_id is not None and not any(
        plant["id"] == record.finding_id for plant in photo["findings"]
    ):
        raise HTTPException(404, "Recorded plant not found on this photo")


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
        effort = summarize_effort(photos, review_history(self.store, run_id, photos))
        sample = audit_sample(run_id, photos)
        blind, late = self.store.latest_audits(run_id), self.store.latest_audits(run_id, False)
        # Per-photo findings stay in the export; the review app sees only counts and who
        # audited, so it can hold a sampled photo out of each auditor's ranked queue.
        audit = summarize_audit(photos, sample, blind, late)
        del audit["findings"]
        photos = [photo | audit_state(photo["id"], sample, blind, late) for photo in photos]
        photos = with_encounters(photos)
        return {
            "run": run,
            "photos": photos,
            "review_effort": effort,
            "audit": audit,
            "references": references,
        }

    def download(self, run_id: str) -> JSONResponse:
        self.run(run_id)
        return JSONResponse(
            export(self.store, run_id),
            headers={
                "Content-Disposition": f'attachment; filename="{run_id}.json"',
            },
        )

    def outcomes(self, run_id: str) -> dict:
        self.run(run_id)
        return outcomes(export(self.store, run_id))

    def image(self, run_id: str, photo_id: str) -> FileResponse:
        photo = self.photo(run_id, photo_id)
        path = (self.store.root / photo["image_path"]).resolve()
        if not path.is_relative_to(self.store.root / "images") or not path.is_file():
            raise HTTPException(404, "Image not available")
        return FileResponse(path, media_type="image/jpeg")

    def review(self, run_id: str, photo_id: str, decision: Review) -> dict:
        try:
            self.store.review(
                run_id,
                photo_id,
                decision.status,
                decision.note,
                decision.reviewer,
                decision.effort_seconds,
            )
        except KeyError as error:
            raise HTTPException(404, "Photo not found") from error
        return {"saved": True}

    def audit(self, run_id: str, photo_id: str, answer: Audit) -> dict:
        photos = self.store.photos(self.run(run_id)["id"])
        if not any(photo["id"] == photo_id for photo in photos):
            raise HTTPException(404, "Photo not found")
        if photo_id not in audit_sample(run_id, photos):
            raise HTTPException(409, "Only audit-sample photos can be audited")
        self.store.audit(
            run_id, photo_id, answer.finding, answer.note, answer.reviewer, answer.effort_seconds
        )
        return {"saved": True}

    def photo(self, run_id: str, photo_id: str) -> dict:
        photos = self.store.photos(self.run(run_id)["id"])
        photo = next((item for item in photos if item["id"] == photo_id), None)
        if photo is None:
            raise HTTPException(404, "Photo not found")
        return photo

    def history(self, run_id: str, photo_id: str) -> list[dict]:
        self.photo(run_id, photo_id)
        return self.store.reviews(run_id, photo_id)

    def record_finding(self, run_id: str, photo_id: str, record: Finding) -> dict:
        check_finding(self.photo(run_id, photo_id)["scores"], record)
        self.store.finding(run_id, photo_id, record)
        return {"saved": True}

    def findings(self, run_id: str, photo_id: str) -> list[dict]:
        return self.photo(run_id, photo_id)["findings"]

    def record_judgement(self, run_id: str, photo_id: str, record: Judgement) -> dict:
        snapshot, [photo] = with_references(self.store.root, [self.photo(run_id, photo_id)])
        check_target(photo, record)
        reason = unsupported(photo, record)
        if reason:
            raise HTTPException(409, reason)
        basis = snapshot["snapshot_sha256"] if snapshot else None
        self.store.judgement(run_id, photo_id, record, basis)
        return {"saved": True}

    def judgements(self, run_id: str, photo_id: str) -> list[dict]:
        self.photo(run_id, photo_id)
        return self.store.judgements(run_id, photo_id)

    def refer(self, run_id: str, photo_id: str, record: Referral) -> dict:
        photo = self.photo(run_id, photo_id)
        plants = {plant["id"] for plant in photo["findings"]}
        if record.finding_id is not None and record.finding_id not in plants:
            raise HTTPException(404, "Recorded plant not found on this photo")
        return {"saved": True, "id": self.store.refer(run_id, photo_id, record)}

    def referrals(self, run_id: str, photo_id: str) -> list[dict]:
        return self.photo(run_id, photo_id)["referrals"]

    def close_referral(
        self, run_id: str, photo_id: str, referral_id: int, event: ReferralEvent
    ) -> dict:
        """Answer or withdraw an open referral; a closed one stays closed."""
        referral = next(
            (item for item in self.referrals(run_id, photo_id) if item["id"] == referral_id),
            None,
        )
        if referral is None:
            raise HTTPException(404, "Referral not found on this photo")
        judgements = self.store.judgements(run_id, photo_id)
        reason = uncitable(referral, judgements, event.judgement_ids)
        if reason:
            raise HTTPException(409, reason)
        try:
            self.store.close_referral(run_id, photo_id, referral_id, event)
        except ValueError as error:
            raise HTTPException(409, str(error)) from error
        return {"saved": True}


def create_app(root: Path, temporal_address: str = "localhost:7234") -> FastAPI:
    app = FastAPI(title="Weedz regional review", version="0.2.0")
    api = ReviewAPI(root, temporal_address)
    app.get("/runs")(api.runs)
    app.post("/runs", status_code=202)(api.start)
    app.get("/runs/{run_id}")(api.detail)
    app.get("/runs/{run_id}/export")(api.download)
    app.get("/runs/{run_id}/outcomes")(api.outcomes)
    app.get("/runs/{run_id}/photos/{photo_id}/image")(api.image)
    app.post("/runs/{run_id}/photos/{photo_id}/review")(api.review)
    app.get("/runs/{run_id}/photos/{photo_id}/reviews")(api.history)
    app.post("/runs/{run_id}/photos/{photo_id}/audit")(api.audit)
    app.post("/runs/{run_id}/photos/{photo_id}/findings")(api.record_finding)
    app.get("/runs/{run_id}/photos/{photo_id}/findings")(api.findings)
    app.post("/runs/{run_id}/photos/{photo_id}/judgements")(api.record_judgement)
    app.get("/runs/{run_id}/photos/{photo_id}/judgements")(api.judgements)
    app.post("/runs/{run_id}/photos/{photo_id}/referrals")(api.refer)
    app.get("/runs/{run_id}/photos/{photo_id}/referrals")(api.referrals)
    app.post("/runs/{run_id}/photos/{photo_id}/referrals/{referral_id}/events")(api.close_referral)
    return app
