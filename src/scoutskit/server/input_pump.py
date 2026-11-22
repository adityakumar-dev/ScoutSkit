"""A person's inputs, applied in order without letting a flood or a slow one hold up the rest.

A trackpad sends dozens of scroll events a second and each one takes the browser a few milliseconds: applied one by one, the queue
grows and the next click waits behind seconds of scrolling. So consecutive scrolls are merged into one, consecutive hovers into the
latest, and a navigation (which can take many seconds on a slow site) runs in the background while clicks and keys carry on.
"""

from __future__ import annotations

import asyncio
from collections import deque
from collections.abc import Awaitable, Callable

SLOW = {"navigate", "new_tab", "back", "reload", "duplicate_tab", "switch_tab", "close_tab"}
MAX_PENDING = 200  # beyond this, the oldest scrolls and hovers are dropped: they only matter as far as the latest one
MAX_SCROLL = 5_000


class InputPump:
    def __init__(self, apply: Callable[[object], Awaitable[str | None]], refuse: Callable[[str], Awaitable[None]]) -> None:
        self._apply, self._refuse = apply, refuse
        self._pending: deque[object] = deque()
        self._wake = asyncio.Event()
        self._slow = asyncio.Lock()
        self._background: set[asyncio.Task] = set()

    def put(self, message: object) -> None:
        """Called by the reader for every message; never waits."""
        self._pending.append(message)
        if len(self._pending) > MAX_PENDING:
            for old in list(self._pending):
                if isinstance(old, dict) and old.get("kind") in ("scroll", "move"):
                    self._pending.remove(old)
                    break
        self._wake.set()

    def _next(self) -> object:
        message = self._pending.popleft()
        if not isinstance(message, dict):
            return message
        kind = message.get("kind")
        if kind not in ("scroll", "move"):
            return message
        merged = dict(message)
        while self._pending and isinstance(self._pending[0], dict) and self._pending[0].get("kind") == kind:
            following = self._pending.popleft()
            merged["x"], merged["y"] = following.get("x"), following.get("y")  # the pointer is where it ended up
            if kind == "scroll":
                try:
                    merged["dy"] = max(-MAX_SCROLL, min(MAX_SCROLL, float(merged.get("dy", 0)) + float(following.get("dy", 0))))
                except (TypeError, ValueError):
                    pass  # left as it is: the validation will refuse it
        return merged

    async def _do(self, message: object) -> None:
        reason = await self._apply(message)
        if reason:
            await self._refuse(reason)

    async def _slowly(self, message: object) -> None:
        async with self._slow:  # navigations one after another, in the order given
            await self._do(message)

    async def run(self) -> None:
        try:
            while True:
                if not self._pending:
                    self._wake.clear()
                    await self._wake.wait()
                    continue
                message = self._next()
                if isinstance(message, dict) and message.get("kind") in SLOW:
                    task = asyncio.create_task(self._slowly(message))
                    self._background.add(task)
                    task.add_done_callback(self._background.discard)
                else:
                    await self._do(message)
        finally:
            for task in self._background:
                task.cancel()
