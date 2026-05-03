from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import AsyncIterator
from typing import Any

logger = logging.getLogger("examcraft.sse")


class EventBus:
    """Per-job pub/sub for SSE. Fan-out to multiple subscribers; replays the
    last N events for late subscribers (so a refresh on the watch page
    catches up instead of starting blank)."""

    def __init__(self, replay: int = 200) -> None:
        self._channels: dict[str, list[asyncio.Queue[dict[str, Any] | None]]] = {}
        self._history: dict[str, list[dict[str, Any]]] = {}
        self._replay = replay
        self._lock = asyncio.Lock()

    async def publish(self, channel: str, event: dict[str, Any]) -> None:
        async with self._lock:
            history = self._history.setdefault(channel, [])
            history.append(event)
            if len(history) > self._replay:
                del history[: len(history) - self._replay]
            queues = list(self._channels.get(channel, []))
        for q in queues:
            await q.put(event)

    async def close(self, channel: str) -> None:
        """Signal subscribers to stop. Future subscribers still see history."""
        async with self._lock:
            queues = list(self._channels.get(channel, []))
        for q in queues:
            await q.put(None)

    async def subscribe(self, channel: str) -> AsyncIterator[dict[str, Any]]:
        queue: asyncio.Queue[dict[str, Any] | None] = asyncio.Queue()
        async with self._lock:
            history = list(self._history.get(channel, []))
            self._channels.setdefault(channel, []).append(queue)
        try:
            for ev in history:
                yield ev
            # If history already contains a "done"/"error" terminal, exit.
            if any(ev.get("event") in {"done", "error"} for ev in history):
                return
            while True:
                ev = await queue.get()
                if ev is None:
                    return
                yield ev
        finally:
            async with self._lock:
                if channel in self._channels:
                    try:
                        self._channels[channel].remove(queue)
                    except ValueError:
                        pass


_BUS = EventBus()


def get_bus() -> EventBus:
    return _BUS


def encode_sse(event_name: str, data: dict[str, Any]) -> bytes:
    """Format one SSE frame."""
    return f"event: {event_name}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n".encode()
