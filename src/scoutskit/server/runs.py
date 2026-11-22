"""Runs the server is working on or has on disk: start, watch, stop, list."""

from __future__ import annotations

import asyncio
import json
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from pydantic import ValidationError

from ..browser import ActionError
from ..control import Decision, PlanGate, RunControl
from ..recorder import RunRecorder
from . import remote_input
from .events import Channel, to_event
from .screencast import Screencast
from .tabs import TabWatcher

RUN_ID = re.compile(r"^\d{8}-\d{6}(-\d+)?$")
MAX_PARALLEL = 3


class TooManyRuns(Exception):
    pass


def _task_of(folder: Path) -> str:
    """The task of a run that never saved a result, from its first log entry."""
    try:
        for line in (folder / "actions.jsonl").read_text(encoding="utf-8").splitlines():
            entry = json.loads(line)
            if entry.get("event") in ("task", "start") and entry.get("task"):
                return str(entry["task"])
    except (OSError, ValueError):
        pass
    return ""


@dataclass
class ActiveRun:
    recorder: RunRecorder
    channel: Channel
    task: str
    control: RunControl = field(default_factory=RunControl, repr=False)
    gate: PlanGate | None = field(default=None, repr=False)  # the plan waits here for approval, unless the run is autonomous
    status: str = "running"
    session: object | None = field(default=None, repr=False)  # the browser being watched (and driven during a take-over)
    worker: asyncio.Task | None = field(default=None, repr=False)
    sessions: dict = field(default_factory=dict, repr=False)  # every sub-agent's browser, by agent id
    focus: str = ""  # the sub-agent being watched
    _screencast: Screencast | None = field(default=None, repr=False)
    _tabs: TabWatcher | None = field(default=None, repr=False)

    async def watch(self, agent: str) -> None:
        """Film and follow another sub-agent's browser. The live view and take-over act on the watched one."""
        await self.unwatch()
        self.channel.last_frame = None  # the other browser's picture must not be shown as this one's
        self.session, self.focus = self.sessions[agent], agent
        self._screencast = Screencast(self.session, self.channel.publish_frame)
        await self._screencast.start()
        self._tabs = TabWatcher(self.session, self.channel.publish)
        self._tabs.start()
        self.channel.publish({"type": "focus", "agent": agent})

    async def unwatch(self) -> None:
        if self._tabs:
            await self._tabs.stop()
        if self._screencast:
            await self._screencast.stop()
        self._tabs = self._screencast = None

    @property
    def id(self) -> str:
        return self.recorder.run_id


class RunManager:
    def __init__(self, runs_dir: Path, execute: Callable, max_parallel: int = MAX_PARALLEL) -> None:
        self.runs_dir, self.execute, self.max_parallel = runs_dir, execute, max_parallel
        self.active: dict[str, ActiveRun] = {}

    # ---- starting and stopping --------------------------------------------------
    def start(self, task: str, *, ask_first: bool = False, **options) -> ActiveRun:
        if sum(1 for run in self.active.values() if run.status == "running") >= self.max_parallel:
            raise TooManyRuns(f"{self.max_parallel} runs are already going; wait for one to finish or stop it")
        recorder = RunRecorder(self.runs_dir)
        run = ActiveRun(recorder, Channel(), task)
        run.control = RunControl(announce=lambda mode: recorder.log(event="control", mode=mode))
        if ask_first:
            run.gate = PlanGate(announce=lambda state, topic: recorder.log(event="approval", state=state, topic=topic))
            options["gate"] = run.gate
        recorder.listeners.append(lambda entry: run.channel.publish(to_event(entry)))
        recorder.listeners.append(lambda entry: self._show_who_needs_help(run, entry))
        self.active[run.id] = run
        run.worker = asyncio.create_task(self._drive(run, options))
        return run

    async def _drive(self, run: ActiveRun, options: dict) -> None:
        async def attach(session, agent: str = "a1") -> None:
            run.sessions[agent] = session
            if not run.focus:
                await run.watch(agent)

        try:
            outcome = await self.execute(run.task, say=lambda text: run.recorder.log(event="notice", text=text),
                                         attach=attach, recorder=run.recorder, control=run.control, **options)
            run.status = outcome.status
            run.channel.publish({"type": "finished", "status": outcome.status, "items": outcome.items, "steps": outcome.steps,
                                 "message": outcome.message, "recipe": outcome.recipe_saved})
        except asyncio.CancelledError:
            run.status = "cancelled"
            run.channel.publish({"type": "finished", "status": "cancelled", "items": 0, "message": "stopped by the user"})
        except Exception as error:  # a run that cannot even start is a result too, not a server crash
            run.status = "failed"
            run.recorder.log(event="error", error=f"{type(error).__name__}: {error}"[:500])
            run.channel.publish({"type": "finished", "status": "failed", "items": 0, "message": str(error)[:500]})
        finally:
            await run.unwatch()
            run.channel.close()

    def take_over(self, run_id: str, mode: str, note: str = "") -> str:
        """'user' asks for the browser (granted when the agent finishes its step); 'agent' hands it back. Returns the control mode now."""
        run = self.active.get(run_id)
        if not run or run.status != "running":
            raise LookupError("that run is not running")
        if mode == "user":
            run.control.request_user()
        else:
            run.control.release(note)
        return run.control.mode

    async def focus(self, run_id: str, agent: str) -> bool:
        run = self.active.get(run_id)
        if not run or run.status != "running" or agent not in run.sessions or run.control.mode != "agent":
            return False  # never switch the browser out from under a person who is driving
        await run.watch(agent)
        return True

    @staticmethod
    def _show_who_needs_help(run: ActiveRun, entry: dict) -> None:
        """A sub-agent asked for a person: show that sub-agent's browser, since that is the one to be driven."""
        agent = entry.get("agent")
        if entry.get("event") == "help_needed" and agent in run.sessions and agent != run.focus:
            asyncio.ensure_future(run.watch(agent))

    def waiting_on(self, run_id: str) -> str:
        """"plan", "result", or "" when the run waits for nothing."""
        run = self.active.get(run_id)
        return run.gate.topic if run and run.gate and run.gate.waiting else ""

    def answer(self, run_id: str, decision: Decision) -> bool:
        run = self.active.get(run_id)
        return bool(run and run.status == "running" and run.gate and run.gate.answer(decision))

    async def remote_input(self, run_id: str, message: object) -> str | None:
        """Apply one click/scroll/type/key from the live view. Returns why it was refused, or None. Never logs the content."""
        run = self.active.get(run_id)
        if not run or run.session is None or not run.control.user_driving:
            return "you are not driving this run: take over first"
        try:
            event = remote_input.parse(message)
        except ValidationError:
            return "that input is not allowed"
        try:
            await remote_input.apply(run.session, event)
        except ActionError as error:  # a refused tool (site policy, a missing tab): the message names no typed text
            return str(error)[:200]
        except Exception:  # the page may be navigating or closed; never surface page content or the typed text
            return "the page did not accept that input"
        return None

    async def stop(self, run_id: str) -> bool:
        run = self.active.get(run_id)
        if not run or run.status != "running" or run.worker is None:
            return False
        run.worker.cancel()
        await asyncio.gather(run.worker, return_exceptions=True)
        return True

    # ---- looking -----------------------------------------------------------------
    def valid(self, run_id: str) -> bool:
        return bool(RUN_ID.match(run_id)) and (self.runs_dir / run_id).is_dir()

    def channel(self, run_id: str) -> Channel | None:
        if run_id in self.active:
            return self.active[run_id].channel
        if not self.valid(run_id):
            return None
        channel = Channel.from_log(self.runs_dir / run_id / "actions.jsonl")
        info = self.summary(run_id) or {}  # the log has no "finished" entry (that is announced live), so the end comes from the result
        channel.events.append({"type": "finished", "status": info.get("status", "interrupted"), "items": info.get("items", 0),
                               "message": "", "recipe": info.get("has_recipe", False)})
        return channel

    def summary(self, run_id: str) -> dict | None:
        if not self.valid(run_id):
            return None
        folder = self.runs_dir / run_id
        info: dict = {"id": run_id, "task": _task_of(folder), "status": "interrupted", "items": 0}  # no result and not running: the server stopped mid-run
        try:
            info.update(json.loads((folder / "result.json").read_text(encoding="utf-8"))["summary"])
        except (OSError, ValueError, KeyError):
            pass
        if run_id in self.active:
            run = self.active[run_id]
            info.update(task=run.task, status=run.status)
        info["id"] = run_id
        info["has_recipe"] = (folder / "recipe.json").exists()
        return info

    def list(self, limit: int = 50) -> list[dict]:
        ids = sorted((p.name for p in self.runs_dir.iterdir() if RUN_ID.match(p.name)), reverse=True) if self.runs_dir.is_dir() else []
        return [self.summary(run_id) for run_id in ids[:limit]]
