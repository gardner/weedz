"""A bounded, process-wide request budget before authentication.

This retains no addresses or tokens. It limits database lookup noise even when tokens
are invalid. A deployment proxy should also bound connections across all workers; this
in-process budget intentionally applies to every HTTP request, including valid tokens.
"""

import math
import threading
import time

from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send


class BeforeAuthentication:
    def __init__(self, app: ASGIApp, rate: float, burst: int) -> None:
        if not math.isfinite(rate) or rate <= 0 or burst < 1:
            raise ValueError("The request rate and burst must be positive")
        self.app, self.rate, self.burst = app, rate, burst
        self.remaining = float(burst)
        self.updated = time.monotonic()
        self._lock = threading.Lock()

    def retry_after(self) -> int:
        with self._lock:
            now = time.monotonic()
            self.remaining = min(self.burst, self.remaining + (now - self.updated) * self.rate)
            self.updated = now
            if self.remaining >= 1:
                self.remaining -= 1
                return 0
            return max(1, math.ceil((1 - self.remaining) / self.rate))

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http" and (wait := self.retry_after()):
            response = JSONResponse(
                {"detail": "The intake is receiving too many requests; retry shortly"},
                status_code=429,
                headers={"Retry-After": str(wait)},
            )
            await response(scope, receive, send)
            return
        await self.app(scope, receive, send)
