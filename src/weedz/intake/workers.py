"""Do not release a submitter's turn while a cancelled request's worker still writes."""

import asyncio
from collections.abc import Callable

from fastapi.concurrency import run_in_threadpool


async def finish_in_thread[**P, T](
    function: Callable[P, T], *args: P.args, **kwargs: P.kwargs
) -> T:
    """Cancellation waits for the worker to finish, then propagates to the request.

    Native asyncio cancellation can abandon Starlette's threadpool await even though the
    thread keeps running. Shield its task, including against repeated cancellation, so a
    surrounding submitter turn cannot be released before the mutation has stopped.
    """
    work = asyncio.create_task(run_in_threadpool(function, *args, **kwargs))
    try:
        return await asyncio.shield(work)
    except asyncio.CancelledError:
        while not work.done():
            try:
                await asyncio.shield(work)
            except asyncio.CancelledError:
                continue
            except Exception:
                break
        if not work.cancelled():
            work.exception()  # retrieve a worker failure before propagating cancellation
        raise
