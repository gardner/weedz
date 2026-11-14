"""The device report intake API (issue #57): its own app, never mounted on the review API.

``PUT /reports/{id}`` sends an approved report under a device-chosen UUID, so a retry on a
flaky connection gets the same receipt instead of a duplicate. ``GET`` returns the
submitter's own receipt and ``DELETE`` withdraws the report. Another submitter's report
is a 404, the same as a missing one. Nothing here logs or echoes a token.
"""

import base64
import binascii
import hashlib
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Request, Response
from pydantic import ValidationError

from weedz.intake.images import ImageRefused, clean_image
from weedz.intake.limits import Limits
from weedz.intake.schema import Report
from weedz.intake.store import Conflict, OverBudget, Receipt, ReportStore, Withdrawn
from weedz.intake.submitters import Submitters, require_submitter


async def read_body(request: Request, limit: int) -> bytes:
    """The JSON body, refused past ``limit`` bytes whether or not a length was declared."""
    if request.headers.get("Content-Type", "").split(";")[0].strip() != "application/json":
        raise HTTPException(415, "Send the report as application/json")
    declared = request.headers.get("Content-Length", "")
    if declared.isdecimal() and int(declared) > limit:
        raise HTTPException(413, f"A report is at most {limit} bytes")
    body = bytearray()
    async for chunk in request.stream():
        body += chunk
        if len(body) > limit:
            raise HTTPException(413, f"A report is at most {limit} bytes")
    return bytes(body)


def parse_report(body: bytes) -> Report:
    try:
        return Report.model_validate_json(body)
    except ValidationError as error:
        # Without the input, so a refused crop or location is not sent back.
        detail = error.errors(include_input=False, include_url=False, include_context=False)
        raise HTTPException(422, detail) from error


def decode_image(report: Report, limits: Limits) -> bytes | None:
    """The report's crop as metadata-free JPEG bytes, or None when it has none."""
    if report.image is None:
        return None
    try:
        data = base64.b64decode(report.image, validate=True)
    except binascii.Error as error:
        raise HTTPException(422, "The image is not valid base64") from error
    if len(data) > limits.max_image_bytes:
        raise HTTPException(413, f"A crop is at most {limits.max_image_bytes} bytes")
    try:
        return clean_image(data, limits.max_pixels)
    except ImageRefused as error:
        raise HTTPException(422, str(error)) from error


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

    async def put(self, report_id: uuid.UUID, request: Request, response: Response) -> Receipt:
        submitter: int = request.state.submitter
        report = parse_report(await read_body(request, self.limits.max_body_bytes))
        key = str(report_id)
        # Canonical, so a retry that differs only in spacing or key order is the same report.
        digest = hashlib.sha256(report.model_dump_json().encode()).hexdigest()
        with refusals():
            earlier = self.store.receipt(submitter, key, digest)
            if earlier:  # a retry: no new work, so no image decoding and no budget
                return earlier
            image = decode_image(report, self.limits)
            receipt, created = self.store.receive(
                submitter, key, report, digest, image, self.limits
            )
        if created:
            response.status_code = 201
        return receipt

    def get(self, report_id: uuid.UUID, request: Request) -> Receipt:
        receipt = self.store.receipt(request.state.submitter, str(report_id))
        return receipt or receipt_missing()

    def delete(self, report_id: uuid.UUID, request: Request) -> Receipt:
        receipt = self.store.withdraw(request.state.submitter, str(report_id))
        return receipt or receipt_missing()


def receipt_missing() -> Receipt:
    raise HTTPException(404, "Report not found")


def create_intake_app(root: Path, limits: Limits | None = None) -> FastAPI:
    """Every route needs a submitter token. No schema or docs are served: the contract
    is documented in the repository, not advertised by the public endpoint."""
    app = FastAPI(
        title="Weedz report intake",
        dependencies=[Depends(require_submitter(Submitters(root)))],
        openapi_url=None,
        docs_url=None,
        redoc_url=None,
    )
    api = IntakeAPI(root, limits or Limits())
    app.put("/reports/{report_id}")(api.put)
    app.get("/reports/{report_id}")(api.get)
    app.delete("/reports/{report_id}")(api.delete)
    return app
