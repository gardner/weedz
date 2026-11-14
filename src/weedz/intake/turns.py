"""Per-submitter turns shared by local server and operator processes.

The lock files are permanent: unlinking one could let newcomers lock a different inode.
The kernel releases ownership when its descriptor closes, including on process death.
This is for a local POSIX filesystem, never SQLite/crops mounted across hosts.
"""

import asyncio
import fcntl
import os
import threading
import time
from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager, contextmanager
from pathlib import Path


class TurnBusy(Exception):
    """Local capacity is full, or the preceding operation exceeded the waiting time."""


class _LocalAdmission:
    """Bound both descriptors and polling tasks, across intake instances in this process."""

    def __init__(self) -> None:
        self._guard = threading.Lock()
        self._pending: dict[tuple[Path, int], int] = {}
        self._total = 0

    @contextmanager
    def enter(self, key: tuple[Path, int]) -> Iterator[None]:
        with self._guard:
            count = self._pending.get(key, 0)
            if count >= 2 or self._total >= 64:
                raise TurnBusy
            self._pending[key] = count + 1
            self._total += 1
        try:
            yield
        finally:
            with self._guard:
                count = self._pending[key] - 1
                if count:
                    self._pending[key] = count
                else:
                    del self._pending[key]
                self._total -= 1


_LOCAL = _LocalAdmission()


class SubmitterTurns:
    def __init__(self, root: Path) -> None:
        self.folder = root.resolve() / "turns"

    def _open(self, submitter: int) -> int:
        self.folder.mkdir(mode=0o700, parents=True, exist_ok=True)
        return os.open(self.folder / f"{submitter}.lock", os.O_CREAT | os.O_RDWR, 0o600)

    @contextmanager
    def _descriptor(self, submitter: int) -> Iterator[int]:
        # Reserve local capacity before opening anything. An open failure releases the
        # slot too; no idle submitter entries or waiter descriptors accumulate.
        with _LOCAL.enter((self.folder, submitter)):
            descriptor = self._open(submitter)
            try:
                yield descriptor
            finally:
                os.close(descriptor)

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
        deadline = time.monotonic() + timeout
        with self._descriptor(submitter) as descriptor:
            while not self._acquire(descriptor):
                if time.monotonic() >= deadline:
                    raise TurnBusy
                time.sleep(min(0.02, max(0, deadline - time.monotonic())))
            yield

    @asynccontextmanager
    async def wait(self, submitter: int, timeout: float) -> AsyncIterator[None]:
        """Wait on the event loop, without occupying an API worker thread."""
        deadline = time.monotonic() + timeout
        with self._descriptor(submitter) as descriptor:
            while not self._acquire(descriptor):
                if time.monotonic() >= deadline:
                    raise TurnBusy
                await asyncio.sleep(min(0.02, max(0, deadline - time.monotonic())))
            yield
