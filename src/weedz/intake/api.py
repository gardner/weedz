"""The device report intake API (issue #57): its own app, never mounted on the review API.

``PUT /reports/{id}`` sends an approved report under a device-chosen UUID, so a retry on a
flaky connection gets the same receipt instead of a duplicate. ``GET`` returns the
submitter's own receipt and ``DELETE`` withdraws the report. Another submitter's report
is a 404, the same as a missing one. Nothing here logs or echoes a token.
"""

import asyncio
import base64
import hashlib
import uuid
from collections.abc import AsyncIterator, Iterator
from contextlib import contextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.concurrency import run_in_threadpool
from pydantic import ValidationError

from weedz import tokens
from weedz.intake.budget import OverBudget
from weedz.intake.deletion import Deletions
from weedz.intake.images import ImageRefused, clean_image
from weedz.intake.limits import Limits
from weedz.intake.schema import Report
from weedz.intake.store import Conflict, Receipt, ReportStore, Withdrawn
from weedz.intake.submitters import Submitters, require_submitter


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
    except OverBudget as error:
        headers = {"Retry-After": str(error.retry_after)}
        raise HTTPException(429, str(error), headers=headers) from error


class IntakeAPI:
    """Each route acts for the submitter that ``require_submitter`` signed in."""

    def __init__(self, root: Path, limits: Limits) -> None:
        self.store = ReportStore(root)
        self.limits = limits
        # Each submitter's uploads and withdrawals are taken in turn, so the budget is checked
        # against every earlier report before any image is decoded, and a withdrawal never
        # slips between checking and storing a report. Waiting is on the event loop, so queued
        # requests hold no worker thread. (One server process, as ``intake serve`` runs.)
        self._submitting: dict[int, asyncio.Lock] = {}

    async def put(self, report_id: uuid.UUID, request: Request, response: Response) -> Receipt:
        submitter: int = request.state.submitter
        # The body is received under the lock too: a withdrawal sent while it arrives waits,
        # and queued uploads are not buffered, as their bodies are not read until their turn.
        async with self._submitting.setdefault(submitter, asyncio.Lock()):
            limits = self.limits
            body = await read_body(request, limits.max_body_bytes, limits.body_idle_seconds)
            # Parsing, image work and SQLite block, so they run off the event loop.
            receipt, created = await run_in_threadpool(self.accept, submitter, str(report_id), body)
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
            image = cleaned_image(upload, self.limits) if upload else None
            return self.store.receive(submitter, report_id, report, digest, image, self.limits)

    def get(self, report_id: uuid.UUID, request: Request) -> Receipt:
        receipt = self.store.receipt(request.state.submitter, str(report_id))
        return receipt or receipt_missing()

    async def delete(self, report_id: uuid.UUID, request: Request) -> Receipt:
        """Taken in turn with the submitter's uploads, so a withdrawal that arrives while
        its report is being stored waits for it and withdraws it, rather than missing it."""
        submitter: int = request.state.submitter
        async with self._submitting.setdefault(submitter, asyncio.Lock()):
            receipt = await run_in_threadpool(self.store.withdraw, submitter, str(report_id))
        return receipt or receipt_missing()


def receipt_missing() -> Receipt:
    raise HTTPException(404, "Report not found")


def create_intake_app(root: Path, limits: Limits | None = None) -> FastAPI:
    """Every route needs a submitter token. No schema or docs are served: the contract
    is documented in the repository, not advertised by the public endpoint."""
    app = FastAPI(
        title="Weedz report intake",
        openapi_url=None,
        docs_url=None,
        redoc_url=None,
    )
    api = IntakeAPI(root, limits or Limits())
    deletions = Deletions(root)
    deletions.resume()
    api.store.sweep()
    authenticated = [Depends(require_submitter(Submitters(root)))]

    def delete_submitter(request: Request) -> dict[str, str | None]:
        submitter = request.state.submitter
        # A revoked secret can only resume an erasure already requested while active.
        if (
            not deletions.started(submitter)
            and Submitters(root).submitter(tokens.bearer(request)) is None
        ):
            raise HTTPException(401, "Send an active submitter token")
        return deletions.delete(submitter).as_dict()

    app.delete(
        "/submitter",
        dependencies=[Depends(require_submitter(Submitters(root), allow_revoked=True))],
    )(delete_submitter)
    app.put("/reports/{report_id}", dependencies=authenticated)(api.put)
    app.get("/reports/{report_id}", dependencies=authenticated)(api.get)
    app.delete("/reports/{report_id}", dependencies=authenticated)(api.delete)
    return app
