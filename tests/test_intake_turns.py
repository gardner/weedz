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


def test_one_submitter_cannot_fill_the_local_waiter_capacity(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    turns = SubmitterTurns(tmp_path)
    original, opened = turns._open, []

    def count(submitter: int) -> int:
        opened.append(submitter)
        return original(submitter)

    monkeypatch.setattr(turns, "_open", count)

    async def waiting() -> None:
        async with turns.wait(1, 2):
            pytest.fail("The preceding operation still holds the turn")

    async def scenario() -> None:
        with turns.take(1, 0.1):
            waiter = asyncio.create_task(waiting())
            try:
                await asyncio.sleep(0.02)

                async def excess() -> None:
                    async with turns.wait(1, 1):
                        pytest.fail("Only one local waiter may open a descriptor")

                for _ in range(50):
                    with pytest.raises(TurnBusy):
                        await asyncio.wait_for(excess(), 0.1)
                assert opened == [1, 1]
                # The overloaded submitter must leave capacity for a different device.
                async with turns.wait(2, 0.1):
                    pass
            finally:
                waiter.cancel()
                with pytest.raises(asyncio.CancelledError):
                    await waiter
        with turns.take(1, 0.1):
            pass  # cancellation released local capacity too

    asyncio.run(scenario())


def test_total_local_capacity_is_bounded_before_opening_files(tmp_path: Path) -> None:
    from contextlib import ExitStack

    turns = SubmitterTurns(tmp_path)
    with ExitStack() as stack:
        for submitter in range(64):
            stack.enter_context(turns.take(submitter, 0.01))
        with pytest.raises(TurnBusy), SubmitterTurns(tmp_path).take(100, 0.01):
            pytest.fail("The total local descriptor allowance is full")
        assert not (turns.folder / "100.lock").exists()
    with turns.take(100, 0.01):
        pass


def test_open_failure_does_not_consume_local_capacity(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    turns = SubmitterTurns(tmp_path)

    def failed(submitter: int) -> int:
        raise OSError("Cannot open lock file")

    with monkeypatch.context() as patch:
        patch.setattr(turns, "_open", failed)
        for _ in range(3):
            with pytest.raises(OSError), turns.take(1, 0.01):
                pytest.fail("Opening failed")
    with turns.take(1, 0.01):
        pass
