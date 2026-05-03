from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable

from sqlalchemy import update

from app.db import _ensure

logger = logging.getLogger("examcraft.jobs")


class JobRegistry:
    """Tracks fire-and-forget asyncio tasks so they're not GC'd mid-flight."""

    def __init__(self) -> None:
        self._tasks: set[asyncio.Task[None]] = set()

    def spawn(self, coro_factory: Callable[[], Awaitable[None]], *, label: str) -> None:
        task = asyncio.create_task(coro_factory(), name=label)
        self._tasks.add(task)

        def _done(t: asyncio.Task[None]) -> None:
            self._tasks.discard(t)
            if t.cancelled():
                return
            exc = t.exception()
            if exc:
                logger.error("Job %s failed: %r", label, exc)

        task.add_done_callback(_done)

    def in_flight(self) -> int:
        return len(self._tasks)


_REGISTRY = JobRegistry()


def get_registry() -> JobRegistry:
    return _REGISTRY


async def mark_in_flight_jobs_failed_on_startup() -> None:
    """Any rows left in extracting/analyzing/running on boot were interrupted by
    a previous shutdown. Mark them as failed so the UI offers retry."""
    from app.models import Bank, GenerationJob, SampleExam

    _, sm = _ensure()
    async with sm() as session:
        await session.execute(
            update(SampleExam)
            .where(SampleExam.status.in_(["extracting", "analyzing"]))
            .values(status="error", error="interrupted by server restart")
        )
        await session.execute(
            update(Bank)
            .where(Bank.analysis_status == "running")
            .values(
                analysis_status="error",
                analysis_error="interrupted by server restart",
            )
        )
        await session.execute(
            update(GenerationJob)
            .where(GenerationJob.status.in_(["queued", "running"]))
            .values(status="failed", error="interrupted by server restart")
        )
        await session.commit()
