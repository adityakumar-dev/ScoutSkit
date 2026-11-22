"""What one run announces, for any number of viewers.

Events (steps, notices, the result) are kept, so a viewer that connects late still sees the whole run.
Frames (the live picture) are not kept, and a slow viewer only ever receives the newest one.
"""

from __future__ import annotations

import asyncio
import json
from collections import deque
from collections.abc import AsyncIterator
from pathlib import Path

Message = dict | bytes  # a dict is an event; bytes are one JPEG frame


def to_event(entry: dict) -> dict:
    """A recorder entry as an event: tool steps are 'step', everything else is named by its 'event' field."""
    return {"type": entry.get("event") or "step", **{k: v for k, v in entry.items() if k != "event"}}


class _Viewer:
    def __init__(self, history: list[dict], frame: bytes | None = None) -> None:
        self.events: deque[dict] = deque(history)
        self.frame: bytes | None = frame  # a viewer that arrives at a page that is not repainting still gets a picture
        self.wake = asyncio.Event()


class Channel:
    def __init__(self) -> None:
        self.events: list[dict] = []
        self.closed = False
        self.last_frame: bytes | None = None
        self._viewers: set[_Viewer] = set()

    @classmethod
    def from_log(cls, actions: Path) -> "Channel":
        """A finished run, rebuilt from the evidence on disk."""
        channel = cls()
        if actions.exists():
            channel.events = [to_event(json.loads(line)) for line in actions.read_text(encoding="utf-8").splitlines() if line.strip()]
        channel.closed = True
        return channel

    def publish(self, event: dict) -> None:
        self.events.append(event)
        for viewer in self._viewers:
            viewer.events.append(event)
            viewer.wake.set()

    def publish_frame(self, jpeg: bytes) -> None:
        self.last_frame = jpeg
        for viewer in self._viewers:
            viewer.frame = jpeg  # replaces any frame the viewer has not taken yet
            viewer.wake.set()

    def close(self) -> None:
        self.closed = True
        for viewer in self._viewers:
            viewer.wake.set()

    async def watch(self) -> AsyncIterator[Message]:
        """Everything so far, then live messages, ending when the run is over."""
        viewer = _Viewer(self.events, self.last_frame)
        self._viewers.add(viewer)
        try:
            while True:
                if viewer.events:
                    yield viewer.events.popleft()
                elif viewer.frame is not None:
                    frame, viewer.frame = viewer.frame, None
                    yield frame
                elif self.closed:
                    return
                else:
                    viewer.wake.clear()
                    await viewer.wake.wait()
        finally:
            self._viewers.discard(viewer)
