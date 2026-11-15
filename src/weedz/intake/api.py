"""The device report intake API (issue #57): its own app, never mounted on the review API.

``PUT /reports/{id}`` sends an approved report under a device-chosen UUID, so a retry on a
flaky connection gets the same receipt instead of a duplicate. ``GET`` returns the
submitter's own receipt and ``DELETE`` withdraws the report. Another submitter's report
is unreadable; withdrawals are scoped to the authenticated submitter.
Nothing here logs or echoes a token.
"""

import asyncio
import base64
import hashlib
import sqlite3
import uuid
from collections.abc import AsyncIterator, Iterator
from contextlib import contextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from weedz import tokens
from weedz.intake.budget import OverBudget
from weedz.intake.deletion import Deletions
from weedz.intake.images import ImageRefused, clean_image
from weedz.intake.limits import Limits
from weedz.intake.schema import Report
from weedz.intake.store import Conflict, Receipt, ReportStore, Withdrawn
from weedz.intake.submitters import Submitters, require_submitter
from weedz.intake.throttle import BeforeAuthentication
from weedz.intake.turns import SubmitterTurns, TurnBusy
from weedz.intake.workers import finish_in_thread


async def read_body(request: Request, limit: int, idle_seconds: float) -> bytes:
    """The JSON body, refused past ``limit`` bytes whether or not a length was declared,
    and with a 408 when no part of it arrives for ``idle_seconds``."""
    if request.headers.get("Content-Type", "").split(";")[0].strip() != "application/json":
        raise HTTPException(415, "Send the report as application/json")
    declared = request.headers.get("Content-Length", "")
    if declared.isdecimal() and int(declared) > limit:
        raise HTTPException(413, f"A report is at most {limit} bytes")
    body, chunks = bytearray(), aiter(request.stream())
    while chunk := await _next_chunk(chunks, idle_seconds):
        body += chunk
        if len(body) > limit:
            raise HTTPException(413, f"A report is at most {limit} bytes")
    return bytes(body)


async def _next_chunk(chunks: AsyncIterator[bytes], idle_seconds: float) -> bytes:
    """The next part of a body, or b"" at its end."""
    try:
        async with asyncio.timeout(idle_seconds):
            return await anext(chunks, b"")
    except TimeoutError as error:
        raise HTTPException(408, "The report stopped arriving") from error


def parse_report(body: bytes) -> Report:
    try:
        return Report.model_validate_json(body)
    except ValidationError as error:
        # Without the input, so a refused crop or location is not sent back.
        detail = error.errors(include_input=False, include_url=False, include_context=False)
        raise HTTPException(422, detail) from error


def uploaded_image(report: Report, limits: Limits) -> bytes | None:
    """The report's crop as sent, or None when it has none."""
    if report.image is None:
        return None
    try:
        data = base64.b64decode(report.image, validate=True)
    except ValueError as error:  # binascii.Error, e.g. for bad padding
        raise HTTPException(422, "The image is not valid base64") from error
    if len(data) > limits.max_image_bytes:
        raise HTTPException(413, f"A crop is at most {limits.max_image_bytes} bytes")
    return data


def cleaned_image(data: bytes, limits: Limits) -> bytes:
    """The crop as metadata-free JPEG bytes, which must also keep within the size limit
    (re-encoding a heavily compressed upload can make it larger)."""
    try:
        cleaned = clean_image(data, limits.max_pixels)
    except ImageRefused as error:
        raise HTTPException(422, str(error)) from error
    if len(cleaned) > limits.max_image_bytes:
        raise HTTPException(413, f"Stored as JPEG, the crop exceeds {limits.max_image_bytes} bytes")
    return cleaned


@contextmanager
def refusals() -> Iterator[None]:
    """The HTTP answer to each reason the store refuses a report."""
    try:
        yield
    except Withdrawn as error:
        raise HTTPException(410, "This report was withdrawn") from error
    except Conflict as error:
        raise HTTPException(409, "This report id was used for a different report") from error
    except TurnBusy as error:
        raise HTTPException(
            503, "The submitter is busy; retry shortly", headers={"Retry-After": "1"}
        ) from error
    except OverBudget as error:
        headers = {"Retry-After": str(error.retry_after)}
        raise HTTPException(429, str(error), headers=headers) from error


class IntakeAPI:
    """Each route acts for the submitter that ``require_submitter`` signed in."""

    def __init__(self, root: Path, limits: Limits) -> None:
        self.store = ReportStore(root, limits.sqlite_busy_seconds)
        self.limits = limits
        self.turns = SubmitterTurns(root)

    async def put(self, report_id: uuid.UUID, request: Request, response: Response) -> Receipt:
        submitter: int = request.state.submitter
        # The body is received under the lock too: a withdrawal sent while it arrives waits,
        # and queued uploads are not buffered, as their bodies are not read until their turn.
        with refusals():
            async with self.turns.wait(submitter, self.limits.submitter_wait_seconds):
                limits = self.limits
                try:
                    async with asyncio.timeout(limits.body_total_seconds):
                        body = await read_body(
                            request, limits.max_body_bytes, limits.body_idle_seconds
                        )
                except TimeoutError as error:
                    raise HTTPException(408, "The report took too long to arrive") from error
                # Parsing, image work and SQLite block, so they run off the event loop.
                receipt, created = await finish_in_thread(
                    self.accept, submitter, str(report_id), body
                )
        if created:
            response.status_code = 201
        return receipt

    def accept(self, submitter: int, report_id: str, body: bytes) -> tuple[Receipt, bool]:
        report = parse_report(body)
        # Canonical, so a retry that differs only in spacing or key order is the same report.
        digest = hashlib.sha256(report.model_dump_json().encode()).hexdigest()
        upload = uploaded_image(report, self.limits)
        with refusals():
            # A retry, or a report over budget, costs no image decoding; any other is
            # charged before decoding, so a crop refused afterwards still costs.
            earlier = self.store.admit(submitter, report_id, digest, bool(upload), self.limits)
            if earlier:
                return earlier, False
            if upload is not None:
                self.store.charge_image_attempt(submitter, report_id, self.limits)
            try:
                image = cleaned_image(upload, self.limits) if upload else None
            except Exception:
                self.store.refused_admission(submitter, report_id)
                raise
            return self.store.receive(submitter, report_id, report, digest, image, self.limits)

    def get(self, report_id: uuid.UUID, request: Request) -> Receipt:
        receipt = self.store.receipt(request.state.submitter, str(report_id))
        return receipt or receipt_missing()

    async def delete(self, report_id: uuid.UUID, request: Request) -> Receipt:
        """Taken in turn with the submitter's uploads, so a withdrawal that arrives while
        its report is being stored waits for it. An earlier withdrawal also records intent,
        so a late upload cannot resurrect it."""
        submitter: int = request.state.submitter
        with refusals():
            async with self.turns.wait(submitter, self.limits.submitter_wait_seconds):
                receipt = await finish_in_thread(
                    self.store.withdraw,
                    submitter,
                    str(report_id),
                    before_arrival=True,
                    limits=self.limits,
                )

        return receipt or receipt_missing()


def receipt_missing() -> Receipt:
    raise HTTPException(404, "Report not found")


def create_intake_app(root: Path, limits: Limits | None = None) -> FastAPI:
    """Every route needs a submitter token, with revoked retry allowed only for erasure."""
    limits = limits or Limits()
    submitters = Submitters(root, limits.sqlite_busy_seconds)
    app = FastAPI(title="Weedz report intake", openapi_url=None, docs_url=None, redoc_url=None)
    app.add_middleware(
        BeforeAuthentication, rate=limits.auth_requests_per_second, burst=limits.auth_burst
    )
    app.add_exception_handler(sqlite3.OperationalError, database_busy)
    api = IntakeAPI(root, limits)
    deletions = Deletions(root, limits.sqlite_busy_seconds)
    deletions.resume()
    api.store.sweep()
    authenticated = [Depends(require_submitter(submitters))]

    def delete_submitter(request: Request) -> dict[str, str | None]:
        submitter = request.state.submitter
        # A revoked secret can only resume an erasure already requested while active.
        if (
            not deletions.started(submitter)
            and submitters.submitter(tokens.bearer(request)) is None
        ):
            raise HTTPException(401, "Send an active submitter token")
        return deletions.delete(submitter).as_dict()

    app.delete(
        "/submitter",
        dependencies=[Depends(require_submitter(submitters, allow_revoked=True))],
    )(delete_submitter)
    app.put("/reports/{report_id}", dependencies=authenticated)(api.put)
    app.get("/reports/{report_id}", dependencies=authenticated)(api.get)
    app.delete("/reports/{report_id}", dependencies=authenticated)(api.delete)
    return app


async def database_busy(request: Request, error: Exception) -> JSONResponse:
    """SQLite contention is retryable; unrelated database failures remain errors."""
    if not isinstance(error, sqlite3.OperationalError) or (
        getattr(error, "sqlite_errorcode", 0) & 0xFF
    ) not in {sqlite3.SQLITE_BUSY, sqlite3.SQLITE_LOCKED}:
        raise error
    return JSONResponse(
        {"detail": "The intake database is busy; retry shortly"},
        status_code=503,
        headers={"Retry-After": "1"},
    )
