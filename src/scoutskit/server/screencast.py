"""The live picture of the browser: Chrome pushes a JPEG whenever the page changes (CDP screencast)."""

from __future__ import annotations

import asyncio
import base64
import contextlib
import time
from collections.abc import Callable

from playwright.async_api import Error as PlaywrightError

from ..browser import BrowserSession

IDLE_SNAPSHOT_S = 1.5  # a page that is not repainting sends no frames: take a still picture so the view is never stale
FOLLOW_EVERY_S = 0.4  # how often to check that the agent is still on the tab being filmed
QUALITY = 60
MAX_SIZE = (1280, 800)


class Screencast:
    def __init__(self, session: BrowserSession, on_frame: Callable[[bytes], None]) -> None:
        self.session, self.on_frame = session, on_frame
        self._page = None
        self._cdp = None
        self._follower: asyncio.Task | None = None
        self._last_frame_at = time.monotonic()

    async def start(self) -> None:
        await self._film(self.session.page)
        self._follower = asyncio.create_task(self._follow())

    async def stop(self) -> None:
        if self._follower:
            self._follower.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._follower
        await self._release()

    async def _film(self, page) -> None:
        try:
            cdp = await self.session.context.new_cdp_session(page)
            cdp.on("Page.screencastFrame", lambda params: asyncio.ensure_future(self._frame(cdp, params)))
            await cdp.send("Page.startScreencast", {"format": "jpeg", "quality": QUALITY, "maxWidth": MAX_SIZE[0], "maxHeight": MAX_SIZE[1]})
        except PlaywrightError:
            return  # the page went away while we were attaching; the follower will try the next one
        self._page, self._cdp = page, cdp

    async def _frame(self, cdp, params: dict) -> None:
        self._last_frame_at = time.monotonic()
        self.on_frame(base64.b64decode(params["data"]))
        with contextlib.suppress(PlaywrightError):  # Chrome sends the next frame only after this acknowledgement
            await cdp.send("Page.screencastFrameAck", {"sessionId": params["sessionId"]})

    async def _release(self) -> None:
        cdp, self._cdp, self._page = self._cdp, None, None
        if cdp:
            with contextlib.suppress(PlaywrightError):
                await cdp.send("Page.stopScreencast")
                await cdp.detach()

    async def _follow(self) -> None:
        """The agent opens and switches tabs: film whichever one it is on now."""
        while True:
            await asyncio.sleep(FOLLOW_EVERY_S)
            if self.session.page is not self._page:
                await self._release()
                await self._film(self.session.page)
            elif time.monotonic() - self._last_frame_at > IDLE_SNAPSHOT_S:
                self._last_frame_at = time.monotonic()
                with contextlib.suppress(Exception):  # evidence for the eye, best effort
                    self.on_frame(await self.session.page.screenshot(type="jpeg", quality=QUALITY, timeout=4_000))
