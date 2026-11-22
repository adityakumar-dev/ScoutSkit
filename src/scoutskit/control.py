"""Who is driving the browser: the agent, or the person watching (take-over).

The agent calls checkpoint() between steps. A take-over is therefore never in the middle of an agent action:
the person asks, the agent finishes its step, then waits until the person hands the browser back.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal

Mode = Literal["agent", "requested", "user"]
TAKEOVER_LIMIT_S = 600  # a forgotten take-over must not hold a run forever


class RunControl:
    def __init__(self, announce: Callable[[str], None] = lambda mode: None, limit_s: float = TAKEOVER_LIMIT_S) -> None:
        self.mode: Mode = "agent"
        self._announce, self._limit = announce, limit_s
        self._handed_back = asyncio.Event()
        self._handed_back.set()
        self._note = ""

    @property
    def user_driving(self) -> bool:
        return self.mode == "user"

    def request_user(self) -> None:
        """Ask for the browser; it is granted at the agent's next checkpoint."""
        if self.mode == "agent":
            self.mode = "requested"
            self._handed_back.clear()
            self._announce("requested")

    def release(self, note: str = "") -> None:
        """Give the browser back to the agent (also cancels a request that has not been granted yet). `note`: "skip" = give up on this site."""
        if self.mode != "agent":
            self._note = note
            self.mode = "agent"
            self._handed_back.set()
            self._announce("agent")

    def take_note(self) -> str:
        """What the person said when they handed back ("" or "skip"); read once."""
        note, self._note = self._note, ""
        return note

    async def checkpoint(self) -> bool:
        """Called by the agent between steps. Waits while the person drives; True if the person drove since the last look."""
        if self.mode == "agent":
            return False
        if self.mode == "requested":
            self.mode = "user"
            self._announce("user")
        try:
            await asyncio.wait_for(self._handed_back.wait(), self._limit)
        except asyncio.TimeoutError:
            self.release()
        return True


@dataclass
class Decision:
    approve: bool
    context: str = ""  # what the user added, when they asked for a new plan


class PlanGate:
    """Where the run waits for the person: to approve the plan (or add context for a new one), and to accept a sub-agent's result."""

    def __init__(self, announce: Callable[[str, str], None] = lambda state, topic: None) -> None:
        self._announce = announce
        self._pending: asyncio.Future[Decision] | None = None
        self.topic = ""

    @property
    def waiting(self) -> bool:
        return self._pending is not None and not self._pending.done()

    async def ask(self, topic: str = "plan") -> Decision:
        """topic: "plan" or "result". One question at a time: a second asker waits for the first answer."""
        while self.waiting:
            await asyncio.shield(self._pending)
        self._pending, self.topic = asyncio.get_running_loop().create_future(), topic
        self._announce("waiting", topic)
        try:
            return await self._pending
        finally:
            self._pending = None

    def answer(self, decision: Decision) -> bool:
        """False when no plan is waiting (already answered, or not asked yet)."""
        if not self.waiting:
            return False
        self._pending.set_result(decision)
        self._announce("approved" if decision.approve else ("revising" if self.topic == "plan" else "rejected"), self.topic)
        return True
