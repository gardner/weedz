"""Local review API. Bind to loopback; Next.js proxies requests on the same origin."""

import tempfile
import uuid
from collections.abc import Iterator
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from temporalio.client import Client

from weedz.discovery.activities import export, review_history
from weedz.discovery.agreed_limits import study_budget
from weedz.discovery.audit import audit_sample, summarize_audit
from weedz.discovery.effort import summarize_effort
from weedz.discovery.encounters import with_encounters
from weedz.discovery.judgements import Judgement, unsupported
from weedz.discovery.leads import LeadEvent, lead_states, no_leads, record_lead, selections
from weedz.discovery.limits import with_limits
from weedz.discovery.occurrences import with_references
from weedz.discovery.outcomes import outcomes
from weedz.discovery.package_output import archive, package_contents
from weedz.discovery.records import SPECIES, TASK_QUEUE, Audit, Finding, Review, RunSpec
from weedz.discovery.referrals import Referral, ReferralEvent, uncitable
from weedz.discovery.sharing import image_use, shareable_export, with_location
from weedz.discovery.store import Store, now
from weedz.discovery.study import NewStudy, StudyDefinition, StudyEdit, StudyLink, terms
from weedz.discovery.study_store import (
    StaleVersion,
    link_study,
    run_study,
    save_version,
    studies,
    versions,
)
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


def check_target(photo: dict, finding_id: int | None, verb: str = "judge") -> None:
    """A judgement or lead is the suggested species or one of this photo's recorded plants."""
    if finding_id is None and not photo["scores"].get("best_species"):
        raise HTTPException(409, f"No suggestion to {verb}; {verb} a recorded plant instead")
    if finding_id is not None and not any(plant["id"] == finding_id for plant in photo["findings"]):
        raise HTTPException(404, "Recorded plant not found on this photo")


def check_lead(photo: dict, record: LeadEvent) -> None:
    """Only the suggestion or a recorded plant on an incidental photo can be a lead."""
    if photo["cohort"] != "incidental":
        raise HTTPException(409, "Only incidental photos can be leads")
    check_target(photo, record.finding_id, "select")


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
        history = review_history(self.store, run_id, photos)
        effort = summarize_effort(photos, history)
        study = run_study(self.store, run_id)
        if study:
            audits = [
                dict(photo_id=photo["id"], events=self.store.audits(run_id, photo["id"]))
                for photo in photos
            ]
            work = {"review_effort": effort, "review_history": history, "audit_history": audits}
            definition = StudyDefinition.model_validate(study["definition"])
            study["budget_use"] = study_budget(work, definition)
        sample = audit_sample(run_id, photos)
        blind, late = self.store.latest_audits(run_id), self.store.latest_audits(run_id, False)
        # Per-photo findings stay in the export; the review app sees only counts and who
        # audited, so it can hold a sampled photo out of each auditor's ranked queue.
        audit = summarize_audit(photos, sample, blind, late)
        del audit["findings"]
        leads = lead_states(selections(self.store, run_id))
        photos = [
            photo
            | audit_state(photo["id"], sample, blind, late)
            | {"lead": leads.get(photo["id"], no_leads())}
            for photo in photos
        ]
        # Obscured points are never served, even to the local review app.
        photos = [with_location(photo, "review") for photo in with_limits(with_encounters(photos))]
        return {
            "run": run,
            "photos": photos,
            "review_effort": effort,
            "audit": audit,
            "references": references,
            "study": study,
        }

    def download(self, run_id: str) -> JSONResponse:
        """The shareable export: no obscured point, and each photo's terms stated. The
        full record stays local, in the store and the completion manifest."""
        self.run(run_id)
        return JSONResponse(
            shareable_export(export(self.store, run_id)),
            headers={
                "Content-Disposition": f'attachment; filename="{run_id}.json"',
            },
        )

    def outcomes(self, run_id: str) -> dict:
        self.run(run_id)
        return outcomes(export(self.store, run_id))

    def studies(self) -> list[dict]:
        return studies(self.store)

    def study(self, study_id: str) -> dict:
        history = versions(self.store, study_id)
        if not history:
            raise HTTPException(404, "Study not found")
        linked = [item["runs"] for item in studies(self.store) if item["id"] == study_id]
        return {"id": study_id, "current": history[-1], "versions": history, "runs": linked[0]}

    def create_study(self, edit: NewStudy) -> dict:
        """A new study, linked to its run in the same request so none is left unlinked."""
        if edit.run_id:
            self.run(edit.run_id)
        saved = self._save_study(None, edit)
        if edit.run_id:
            link_study(self.store, edit.run_id, saved["id"], edit.author)
        return saved

    def edit_study(self, study_id: str, edit: StudyEdit) -> dict:
        self.study(study_id)
        return self._save_study(study_id, edit)

    def _save_study(self, study_id: str | None, edit: StudyEdit) -> dict:
        try:
            return save_version(self.store, study_id, edit)
        except StaleVersion as error:
            raise HTTPException(409, str(error)) from error

    def run_study(self, run_id: str) -> dict | None:
        self.run(run_id)
        return run_study(self.store, run_id)

    def link_study(self, run_id: str, link: StudyLink) -> dict:
        self.run(run_id)
        try:
            link_study(self.store, run_id, link.study_id, link.linked_by)
        except KeyError as error:
            raise HTTPException(404, "Study not found") from error
        return {"saved": True}

    def package(self, run_id: str) -> dict:
        """The selected leads only, as JSON; photos are in the archive."""
        self.run(run_id)
        return package_contents(self.store, run_id, now())[0]

    def package_archive(self, run_id: str) -> StreamingResponse:
        """The package as a zip, built in a temporary file before any byte is sent (so a
        photo that changed is refused with 409, not truncated) and then streamed."""
        self.run(run_id)
        package, photos = package_contents(self.store, run_id, now())
        spool = tempfile.TemporaryFile()  # noqa: SIM115 - closed once streamed or refused
        try:
            archive(package, photos, spool)
        except (ValueError, OSError) as error:
            spool.close()
            # A retained photo changed or vanished after it was checked; name no local path.
            reason = str(error) if isinstance(error, ValueError) else "A photo could not be read"
            raise HTTPException(409, f"{reason}; package again") from error
        spool.seek(0)

        def chunks() -> Iterator[bytes]:
            with spool:
                yield from iter(lambda: spool.read(1 << 16), b"")

        return StreamingResponse(
            chunks(),
            media_type="application/zip",
            headers={"Content-Disposition": f'attachment; filename="{run_id}-follow-up.zip"'},
        )

    def image(self, run_id: str, photo_id: str) -> FileResponse:
        photo = self.photo(run_id, photo_id)
        allowed = image_use(photo, "review")
        if allowed.action != "show":
            raise HTTPException(403, allowed.reason)
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
        check_target(photo, record.finding_id)
        reason = unsupported(photo, record)
        if reason:
            raise HTTPException(409, reason)
        basis = snapshot["snapshot_sha256"] if snapshot else None
        self.store.judgement(run_id, photo_id, record, basis)
        return {"saved": True}

    def judgements(self, run_id: str, photo_id: str) -> list[dict]:
        self.photo(run_id, photo_id)
        return self.store.judgements(run_id, photo_id)

    def select_lead(self, run_id: str, photo_id: str, record: LeadEvent) -> dict:
        check_lead(self.photo(run_id, photo_id), record)
        if not record_lead(self.store, run_id, photo_id, record):
            selected = record.action == "selected"
            raise HTTPException(
                409, "Already selected" if selected else "This lead is not selected"
            )
        return {"saved": True}

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
        reason = uncitable(referral, judgements, event)
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
    app.get("/runs/{run_id}/study")(api.run_study)
    app.post("/runs/{run_id}/study")(api.link_study)
    app.get("/studies")(api.studies)
    # Before /studies/{study_id}, which would otherwise take "terms" as an id.
    app.get("/studies/terms")(terms)
    app.post("/studies", status_code=201)(api.create_study)
    app.get("/studies/{study_id}")(api.study)
    app.post("/studies/{study_id}/versions", status_code=201)(api.edit_study)
    app.get("/runs/{run_id}/package")(api.package)
    app.get("/runs/{run_id}/package/archive")(api.package_archive)
    app.get("/runs/{run_id}/photos/{photo_id}/image")(api.image)
    app.post("/runs/{run_id}/photos/{photo_id}/review")(api.review)
    app.get("/runs/{run_id}/photos/{photo_id}/reviews")(api.history)
    app.post("/runs/{run_id}/photos/{photo_id}/audit")(api.audit)
    app.post("/runs/{run_id}/photos/{photo_id}/findings")(api.record_finding)
    app.get("/runs/{run_id}/photos/{photo_id}/findings")(api.findings)
    app.post("/runs/{run_id}/photos/{photo_id}/judgements")(api.record_judgement)
    app.get("/runs/{run_id}/photos/{photo_id}/judgements")(api.judgements)
    app.post("/runs/{run_id}/photos/{photo_id}/leads")(api.select_lead)
    app.post("/runs/{run_id}/photos/{photo_id}/referrals")(api.refer)
    app.get("/runs/{run_id}/photos/{photo_id}/referrals")(api.referrals)
    app.post("/runs/{run_id}/photos/{photo_id}/referrals/{referral_id}/events")(api.close_referral)
    return app
