"""Approved device reports as review items in their own run (issue #58).

The only bridge from report intake (#57) to review. Each received, non-withdrawn report
becomes an item in the ``device-reports`` run, in its own ``device`` cohort, so it never
changes an iNaturalist run's counts. It keeps its provenance: the submitter (by number,
never the operator's label), the app version and the screening model stamp. The device's
location is exact and was never obscured, so it is kept as sent, with its accuracy. A crop
is copied into the review store only with image consent, under the licence chosen then.

``sync`` runs before every request that reads the run. When a report has been withdrawn,
its item leaves the queue: its image copy is deleted and its location, capture time and
credit are erased. Its id, candidate and model stamp stay, so the append-only reviews,
judgements, referrals and lead events made on it still read sensibly.
"""

import fcntl
import hashlib
import json
import os
import time
import uuid
from io import BytesIO
from pathlib import Path
from typing import Literal

from PIL import Image
from pydantic import BaseModel

from weedz import consent
from weedz.discovery.records import SPECIES
from weedz.discovery.sharing import withdrawn
from weedz.discovery.store import Store, now
from weedz.intake.store import ReportStore, StoredReport

RUN_ID = "device-reports"
IMAGES = "images/device"
LOCK = "device-reports.lock"
# A temporary crop older than this is left from a failed write, not one in progress.
STALE_WRITE_SECONDS = 600
# A report without a photo licence shares nothing under one, so it gets no credit line.
NO_LICENCE = "Device report (no photo licence)"


class Provenance(BaseModel):
    """Where a device report came from and what screened it."""

    submitter: int
    report_id: str
    received_at: str
    captured_at: str | None
    app_version: str
    model_key: str
    revision: str
    ranking_revision: int
    score_meaning: str | None
    consent_wording: str
    image_consent: bool
    # Whether the person agreed to share the exact point (#91); a point is sent only then.
    location_consent: bool


class ContributorConsent(BaseModel):
    """What the person permitted, as the sharing policy reads it (#60). ``withdrawn_at`` is
    when review learned of the withdrawal; the item then carries no personal detail."""

    version: str
    uses: list[str]
    withdrawn_at: str | None = None


class DeviceItem(BaseModel):
    """A device report in the shape every review path reads."""

    id: str
    region: str = "device"
    cohort: Literal["device"] = "device"
    reference_species: None = None
    source_url: str = ""
    image_url: str = ""
    attribution: str
    photo_license: str
    observation_license: str
    observer: str
    original_taxon: str
    original_common_name: str
    observed_on: str | None
    uploaded_at: str
    latitude: float | None
    longitude: float | None
    positional_accuracy_m: float | None
    coordinate_status: Literal["public", "missing"]
    image_path: str = ""
    sha256: str = ""
    device: Provenance
    consent: ContributorConsent


def item_id(stored: StoredReport) -> str:
    return f"device-{stored.submitter}-{stored.report_id}"


def item(stored: StoredReport) -> DeviceItem:
    """The review item for a stored report, before any image is copied."""
    content, location = stored.report, stored.report.location
    licence = content.consent.licence or ""
    taxon = content.candidate.taxon
    captured = content.captured_at
    return DeviceItem(
        id=item_id(stored),
        # The credit as the consent text promised it, a blank one as "a Weedz contributor".
        attribution=consent.attribution(licence, content.consent.credit) if licence else NO_LICENCE,
        photo_license=licence,
        observation_license=licence,
        observer=f"submitter {stored.submitter}",
        original_taxon=taxon,
        original_common_name=SPECIES[taxon],
        # The calendar day in the device's own offset: the day the person saw.
        observed_on=captured.date().isoformat() if captured else None,
        uploaded_at=stored.received_at,
        latitude=location.latitude if location else None,
        longitude=location.longitude if location else None,
        positional_accuracy_m=location.accuracy_m if location else None,
        coordinate_status="public" if location else "missing",
        consent=ContributorConsent(
            version=content.consent.wording_version, uses=sorted(content.consent.uses)
        ),
        device=Provenance(
            submitter=stored.submitter,
            report_id=stored.report_id,
            received_at=stored.received_at,
            captured_at=captured.isoformat() if captured else None,
            app_version=content.app_version,
            model_key=content.model.model_key,
            revision=content.model.revision,
            ranking_revision=content.model.ranking_revision,
            score_meaning=content.model.score_meaning,
            consent_wording=content.consent.wording_version,
            image_consent=content.consent.image,
            location_consent=content.consent.location,
        ),
    )


def scores(stored: StoredReport) -> dict:
    """The device's suggestion: a margin from on-device screening, not a verdict."""
    candidate, model = stored.report.candidate, stored.report.model
    method = f"On-device screening: {model.model_key} {model.revision}"
    return {"best_species": candidate.taxon, "margin": candidate.score, "method": method}


def _crop(stored: StoredReport, record: DeviceItem) -> bytes | None:
    """The consented crop's bytes, or None when there is none to copy."""
    if stored.image is None or not record.device.image_consent:
        return None
    try:
        return stored.image.read_bytes()
    except FileNotFoundError:  # withdrawn after it was listed
        return None


def _write_private(target: Path, data: bytes) -> None:
    target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    # Its own temporary name, so two syncs at once never write into the same file.
    temporary = target.with_suffix(f".{uuid.uuid4().hex}.tmp")
    descriptor = os.open(temporary, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    try:
        with os.fdopen(descriptor, "wb") as out:
            out.write(data)
        temporary.replace(target)
    finally:
        temporary.unlink(missing_ok=True)


def _names(store: Store, identifier: str, image_path: str) -> bool:
    with store.connect() as db:
        row = db.execute(
            "SELECT record FROM photos WHERE run_id=? AND id=?", (RUN_ID, identifier)
        ).fetchone()
    return row is not None and json.loads(row["record"])["image_path"] == image_path


def _add(store: Store, stored: StoredReport) -> None:
    """Add a report. Its row names the crop before the crop is written, so every copy on
    disk is one a withdrawal can find and delete."""
    record, found = item(stored), scores(stored)
    data = _crop(stored, record)
    if data:
        with Image.open(BytesIO(data)) as image:
            found.update(width=image.width, height=image.height)
        record.image_path = f"{IMAGES}/{record.id}.jpg"
        record.sha256 = hashlib.sha256(data).hexdigest()
    with store.connect() as db:
        cursor = db.execute(
            "INSERT OR IGNORE INTO photos(run_id,id,record,scores) VALUES(?,?,?,?)",
            (RUN_ID, record.id, record.model_dump_json(), json.dumps(found)),
        )
    if data and cursor.rowcount == 1:
        _store_crop(store, record.id, record.image_path, data)


def _store_crop(store: Store, identifier: str, image_path: str, data: bytes) -> None:
    """Write the crop its row names; delete it again if withdrawn while it was written."""
    target = store.root / image_path
    _write_private(target, data)
    # Withdrawn meanwhile: the erase may have run before the file existed.
    if not _names(store, identifier, image_path):
        target.unlink(missing_ok=True)


def _restore(store: Store, stored: StoredReport, record: dict) -> None:
    """Copy again a crop whose earlier copy did not complete (a full disk, a crash)."""
    if (store.root / record["image_path"]).exists():
        return
    data = _crop(stored, DeviceItem.model_validate(record))
    if data and hashlib.sha256(data).hexdigest() == record["sha256"]:
        _store_crop(store, record["id"], record["image_path"], data)


def _erased(record: dict) -> dict:
    """A withdrawn report's item, with its personal details erased."""
    erased = {"latitude": None, "longitude": None, "positional_accuracy_m": None}
    return (
        record
        | erased
        | {
            "coordinate_status": "missing",
            "observed_on": None,
            "attribution": "",
            "image_path": "",
            "sha256": "",
            "device": record["device"] | {"captured_at": None},
            "consent": record["consent"] | {"withdrawn_at": now()},
        }
    )


def _withdraw(store: Store, identifier: str, record: dict) -> None:
    """Erase the record, zeroing the old bytes in the database and its log, then delete
    the crop. The record goes first, so a crop written meanwhile is found and deleted."""
    with store.connect() as db:
        db.execute("PRAGMA secure_delete=ON")
        db.execute(
            "UPDATE photos SET record=? WHERE run_id=? AND id=?",
            (json.dumps(_erased(record)), RUN_ID, identifier),
        )
    with store.connect() as db:
        db.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    if record.get("image_path"):
        (store.root / record["image_path"]).unlink(missing_ok=True)


def _sweep(store: Store) -> None:
    """Delete crops no current row names, such as one left by a crash between a
    withdrawal's erase and its deletion. A crop is written only after its row, so a live
    one is never swept; one swept as it was written is copied again next sync. A
    temporary file is left while a write may still be using it."""
    folder = store.root / IMAGES
    if not folder.is_dir():
        return
    with store.connect() as db:
        rows = db.execute("SELECT record FROM photos WHERE run_id=?", (RUN_ID,))
        named = {json.loads(row["record"])["image_path"] for row in rows}
    stale = time.time() - STALE_WRITE_SECONDS
    for path in folder.iterdir():
        if path.suffix == ".tmp" and path.stat().st_mtime > stale:
            continue
        if f"{IMAGES}/{path.name}" not in named:
            path.unlink(missing_ok=True)


def _create_run(store: Store) -> None:
    """The device run, without a query spec: it is not a bounded historical query."""
    with store.connect() as db:
        db.execute(
            "INSERT OR IGNORE INTO runs(id,created_at,spec,status) VALUES(?,?,?,?)",
            (RUN_ID, now(), "{}", "receiving"),
        )


def _withdrawn(reports: ReportStore, record: dict) -> bool:
    """Whether intake says the person withdrew it. A report merely missing, as from a
    wrong or empty intake folder, is left alone rather than erased."""
    device = record["device"]
    receipt = reports.receipt(device["submitter"], device["report_id"])
    return receipt is not None and receipt.status == "withdrawn"


def _private(store: Store) -> None:
    """Device reports hold exact locations, so the review database is owner-only."""
    for suffix in ("", "-wal", "-shm"):
        path = store.database.with_name(store.database.name + suffix)
        if path.exists():
            path.chmod(0o600)


def sync(store: Store, reports: ReportStore) -> None:
    """Bring the device run up to date with intake: add new reports, erase withdrawn ones.
    Syncs take turns, across processes too, so one that listed a report before it was
    withdrawn never writes it back after a later sync erased it."""
    with (store.root / LOCK).open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        _sync(store, reports)


def _sync(store: Store, reports: ReportStore) -> None:
    _create_run(store)
    _private(store)
    active = {item_id(stored): stored for stored in reports.active()}
    with store.connect() as db:
        rows = db.execute("SELECT id, record FROM photos WHERE run_id=?", (RUN_ID,))
        known = {row["id"]: json.loads(row["record"]) for row in rows}
    for identifier, stored in active.items():
        if identifier not in known:
            _add(store, stored)
        elif known[identifier].get("image_path"):
            _restore(store, stored, known[identifier])
    gone = 0
    for identifier, record in known.items():
        if withdrawn(record):
            gone += 1
        elif identifier not in active and _withdrawn(reports, record):
            _withdraw(store, identifier, record)
            gone += 1
    _sweep(store)
    detail = f"{len(active)} reports in review · {gone} withdrawn"
    store.status(RUN_ID, "receiving", detail)
