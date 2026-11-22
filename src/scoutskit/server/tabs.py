"""The browser's tabs, announced to the viewers whenever they change (a new tab, a title that finishes loading, a switch)."""

from __future__ import annotations

import asyncio
import contextlib
from collections.abc import Callable

from ..browser import BrowserSession

WATCH_EVERY_S = 0.5
TITLE_WAIT_S = 1.0  # a page that is still loading may not answer for its title
MAX_TITLE = 80


class TabWatcher:
    def __init__(self, session: BrowserSession, publish: Callable[[dict], None]) -> None:
        self.session, self.publish = session, publish
        self._last: list[dict] | None = None
        self._task: asyncio.Task | None = None

    def start(self) -> None:
        self._task = asyncio.create_task(self._watch())

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task

    async def snapshot(self) -> list[dict]:
        tabs = []
        for index, page in enumerate(self.session.tabs()):
            try:
                title = await asyncio.wait_for(page.title(), TITLE_WAIT_S)
            except Exception:  # loading, navigating or just closed
                title = ""
            tabs.append({"index": index, "title": title[:MAX_TITLE], "url": page.url, "active": page is self.session.page})
        return tabs

    async def _watch(self) -> None:
        while True:
            tabs = await self.snapshot()
            if tabs != self._last:
                self._last = tabs
                self.publish({"type": "tabs", "tabs": tabs})
            await asyncio.sleep(WATCH_EVERY_S)
