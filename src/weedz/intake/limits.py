"""How much one request, and one submitter per day, may send (placeholders for a pilot)."""

from dataclasses import dataclass

DAY_SECONDS = 24 * 60 * 60


@dataclass(frozen=True)
class Limits:
    # A report's JSON, including a base64 crop (a third larger than the image).
    max_body_bytes: int = 2_000_000
    # How long a body may take to arrive: a phone that drops off mid-upload must not hold
    # its submitter's turn (and so its retries and withdrawals) indefinitely.
    body_seconds: float = 60
    max_image_bytes: int = 1_000_000
    # Checked from the image header before decoding, so a decompression bomb is refused.
    max_pixels: int = 4096 * 4096
    # Per submitter over the last 24 hours, counting withdrawn reports too.
    reports_per_day: int = 100
    image_bytes_per_day: int = 50_000_000
