"""Per-submitter turns shared by local server and operator processes.

The lock files are permanent: unlinking one could let newcomers lock a different inode.
The kernel releases ownership when its descriptor closes, including on process death.
This is for a local POSIX filesystem, never SQLite/crops mounted across hosts.
"""

import asyncio
import fcntl
import os
import time
from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager, contextmanager
from pathlib import Path


class TurnBusy(Exception):
    """The preceding operation did not finish within the configured waiting time."""


class SubmitterTurns:
    def __init__(self, root: Path) -> None:
        self.folder = root / "turns"

    def _open(self, submitter: int) -> int:
        self.folder.mkdir(mode=0o700, parents=True, exist_ok=True)
        return os.open(self.folder / f"{submitter}.lock", os.O_CREAT | os.O_RDWR, 0o600)

    @staticmethod
    def _acquire(descriptor: int) -> bool:
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
            return True
        except BlockingIOError:
            return False

    @contextmanager
    def take(self, submitter: int, timeout: float) -> Iterator[None]:
        """An operator's bounded wait; it never holds the reports database write lock."""
        descriptor, deadline = self._open(submitter), time.monotonic() + timeout
        try:
            while not self._acquire(descriptor):
                if time.monotonic() >= deadline:
                    raise TurnBusy
                time.sleep(min(0.02, max(0, deadline - time.monotonic())))
            yield
        finally:
            os.close(descriptor)

    @asynccontextmanager
    async def wait(self, submitter: int, timeout: float) -> AsyncIterator[None]:
        """Wait on the event loop, without occupying an API worker thread."""
        descriptor, deadline = self._open(submitter), time.monotonic() + timeout
        try:
            while not self._acquire(descriptor):
                if time.monotonic() >= deadline:
                    raise TurnBusy
                await asyncio.sleep(min(0.02, max(0, deadline - time.monotonic())))
            yield
        finally:
            os.close(descriptor)
