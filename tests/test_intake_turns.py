"""One submitter's turn is shared by independent processes, without stale leases."""

import asyncio
import multiprocessing
import time
from multiprocessing.synchronize import Event
from pathlib import Path

import pytest

from weedz.intake.turns import SubmitterTurns, TurnBusy


def hold(root: Path, entered: Event) -> None:
    with SubmitterTurns(root).take(1, 1):
        entered.set()
        time.sleep(10)


def test_processes_share_turns_and_death_releases_ownership(tmp_path: Path) -> None:
    context = multiprocessing.get_context("spawn")
    entered = context.Event()
    worker = context.Process(target=hold, args=(tmp_path, entered))
    worker.start()
    try:
        assert entered.wait(5)
        turns = SubmitterTurns(tmp_path)
        with pytest.raises(TurnBusy), turns.take(1, 0.02):
            pytest.fail("The other process still owns the turn")
        with turns.take(2, 0.02):
            pass  # another submitter is independent
        worker.terminate()
        worker.join(5)
        assert not worker.is_alive()
        with turns.take(1, 0.1):
            pass
    finally:
        if worker.is_alive():
            worker.terminate()
        worker.join(5)


def test_cancelled_waiter_neither_owns_nor_releases_another_turn(tmp_path: Path) -> None:
    turns = SubmitterTurns(tmp_path)

    async def waiting() -> None:
        async with turns.wait(1, 2):
            pytest.fail("Should not acquire an occupied turn")

    async def scenario() -> None:
        with turns.take(1, 0.1):
            waiter = asyncio.create_task(waiting())
            await asyncio.sleep(0.02)
            waiter.cancel()
            with pytest.raises(asyncio.CancelledError):
                await waiter
            with pytest.raises(TurnBusy), turns.take(1, 0.02):
                pass
        async with turns.wait(1, 0.1):
            pass

    asyncio.run(scenario())
