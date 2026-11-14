"""Shared builders for the device report intake tests (issue #57)."""

import base64
import uuid
from io import BytesIO
from typing import Any

from PIL import Image


def report(**changes: Any) -> dict:
    """A valid version-1 report, with top-level fields replaced by ``changes``."""
    body: dict[str, Any] = {
        "schema_version": 1,
        "app_version": "0.1.0",
        "candidate": {"taxon": "Ulex europaeus", "score": 0.12},
        "model": {
            "model_key": "bioclip-2",
            "revision": "f2b4c1d",
            "ranking_revision": 4,
            "score_meaning": "bioclip-2/ranking-4/meaning-1",
        },
        "captured_at": "2026-10-01T10:00:00+13:00",
        "location": {"latitude": -41.27, "longitude": 173.28, "accuracy_m": 25},
        "consent": {"wording_version": "2026-11", "image": False},
    }
    return body | changes


def with_image(
    data: bytes,
    licence: str = "cc-by",
    uses: tuple[str, ...] | list[str] = ("review",),
    credit: str | None = None,
    **changes: Any,
) -> dict:
    consent = {"wording_version": "2026-11", "image": True, "uses": list(uses), "licence": licence}
    if credit is not None:
        consent["credit"] = credit
    return report(image=base64.b64encode(data).decode(), consent=consent, **changes)


def jpeg(size: tuple[int, int] = (64, 48), **save: Any) -> bytes:
    out = BytesIO()
    Image.new("RGB", size, (40, 120, 40)).save(out, "JPEG", **save)
    return out.getvalue()


def jpeg_with_gps() -> bytes:
    """A JPEG carrying the private metadata a phone photo would: GPS, camera, XMP."""
    exif = Image.Exif()
    exif[0x010F] = "PhoneMaker"  # Make
    exif[0xA431] = "SERIAL-123456"  # BodySerialNumber
    exif[0x8825] = {1: "S", 2: (41.0, 16.0, 12.0), 3: "E", 4: (173.0, 17.0, 0.0)}  # GPS IFD
    xmp = b'<x:xmpmeta xmlns:x="adobe:ns:meta/">HomeAddress</x:xmpmeta>'
    return jpeg(exif=exif, xmp=xmp, comment=b"secret comment")


def new_id() -> str:
    return str(uuid.uuid4())
