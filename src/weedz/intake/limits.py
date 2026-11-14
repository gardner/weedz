"""How much one request, and one submitter per day, may send (placeholders for a pilot)."""

import math
from dataclasses import dataclass

DAY_SECONDS = 24 * 60 * 60


@dataclass(frozen=True)
class Limits:
    # A report's JSON, including a base64 crop (a third larger than the image).
    max_body_bytes: int = 2_000_000
    # The longest gap allowed between parts of a body: a phone that drops off mid-upload
    # must not hold its submitter's turn (and so retries and withdrawals) for ever.
    # The total body deadline separately bounds even a steady trickle.
    body_idle_seconds: float = 30
    body_total_seconds: float = 120
    sqlite_busy_seconds: float = 5
    submitter_wait_seconds: float = 130
    # Pre-authentication requests, across all clients of one server process.
    auth_requests_per_second: float = 100
    auth_burst: int = 200
    max_image_bytes: int = 1_000_000
    # Checked from the image header before decoding, so a decompression bomb is refused.
    max_pixels: int = 4096 * 4096
    # Per submitter over the last 24 hours, counting withdrawn reports too.
    reports_per_day: int = 100
    image_bytes_per_day: int = 50_000_000

    def __post_init__(self) -> None:
        for name in (
            "body_idle_seconds",
            "body_total_seconds",
            "submitter_wait_seconds",
            "auth_requests_per_second",
        ):
            value = getattr(self, name)
            if not math.isfinite(value) or value <= 0:
                raise ValueError(f"{name} must be finite and positive")
        if not math.isfinite(self.sqlite_busy_seconds) or self.sqlite_busy_seconds < 0:
            raise ValueError("sqlite_busy_seconds must be finite and nonnegative")
        if self.auth_burst < 1:
            raise ValueError("auth_burst must be positive")
