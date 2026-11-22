"""The main brain's team: one sub-agent per picked source, working in parallel, each in its own browser context.

When a sub-agent finishes, the brain checks its result against the task. In autonomous mode the brain's verdict
decides; otherwise the person confirms it. The first accepted result wins and every other sub-agent is stopped.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import re
from urllib.parse import urlsplit
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field, replace

from .agent import Agent, AgentResult, TaskPlan
from .brief import Brief
from .browser import ActionError, BrowserHost, BrowserSession, FileStore, looks_like_file
from .control import PlanGate, RunControl
from .provider.llm import LLMError, complete_json
from .recorder import RunRecorder
from .search import Hit, same_page

MAX_AGENTS = 3
SPARE_STEPS = 15  # a replacement for a failed scout gets a shorter leash: the picks it falls back on are less certain
REFUSED = re.compile(r"HTTP (?:403|418|429)|block page|CAPTCHA", re.I)  # the site refused the browser: its other pages will be refused too
SAMPLE_ROWS = 5

VERIFY_SYSTEM = """You are the main brain checking a sub-agent's result before the user gets it. Reply with one JSON object:
{"complete": true or false, "why": "<one sentence>"}
You are shown only the first few items as a sample: the item count is exact and the whole list is in the result, so never treat the sample's size as the result's size.
complete = the result fully answers the TASK: the right items or files, from a credible source. Part of the answer, the wrong kind of item,
or an unofficial copy when the official source was available, is not complete."""


@dataclass
class Member:
    id: str
    name: str
    pick: Hit
    spare: bool = False  # started as a replacement for a scout that found nothing
    session: BrowserSession | None = None
    result: AgentResult | None = None
    error: str = ""
    files: list = field(default_factory=list)

    @property
    def found(self) -> int:
        return (len(self.result.rows) if self.result else 0) + len(self.files)


@dataclass
class TeamResult:
    members: list[Member]
    winner: Member | None
    verdict: str  # why the winner was accepted, or why nothing was

    @property
    def best(self) -> Member:
        """The winner, else whoever found the most."""
        return self.winner or max(self.members, key=lambda m: (m.found, m.result is not None))


def distinct_picks(brief: Brief) -> list[Hit]:
    """The brain's picks as distinct pages, best first; the plan's start page when it picked none."""
    picks, seen = [], set()
    for hit in [hit for hit, _ in brief.picks] or [Hit("start", brief.plan.start_url, "", "plan")]:
        if same_page(hit.url) not in seen:
            seen.add(same_page(hit.url))
            picks.append(hit)
    return picks


def team_picks(brief: Brief, size: int) -> list[Hit]:
    """The sources the sub-agents start from at first."""
    return distinct_picks(brief)[: max(1, min(size, MAX_AGENTS))]


class Team:
    def __init__(
        self, host: BrowserHost, brief: Brief, task: str, *, providers: list, make_models: Callable[[], list], recorder: RunRecorder,
        max_steps: int, web: bool, control: RunControl | None = None, gate: PlanGate | None = None,
        attach: Callable[[BrowserSession, str], Awaitable[None]] | None = None, say: Callable[[str], None] = lambda _: None,
        search: Callable | None = None, budget=None,
    ) -> None:
        self.budget = budget  # shared with every sub-agent
        self.search = search  # async (query) -> [Hit], given to every sub-agent as the web_search tool
        self.host, self.brief, self.task, self.providers, self.make_models = host, brief, task, providers, make_models
        self.rec, self.max_steps, self.web, self.control, self.gate, self.attach, self.say = recorder, max_steps, web, control, gate, attach, say

    async def run(self) -> TeamResult:
        picks = distinct_picks(self.brief)
        first = max(1, min(self.brief.agents, MAX_AGENTS, len(picks)))
        spare = picks[first:]  # picks nobody started from: tried one by one when a sub-agent finds nothing
        members: list[Member] = []
        work: dict[asyncio.Task, Member] = {}
        refused_hosts: set[str | None] = set()

        def start(pick: Hit, spare: bool = False) -> Member:
            member = Member(f"a{len(members) + 1}", "", pick, spare)
            member.name = f"Scout {len(members) + 1}" if (first > 1 or spare) else "Main agent"
            members.append(member)
            work[asyncio.create_task(self._work(member))] = member
            return member

        for pick in picks[:first]:
            start(pick)
        if first > 1:
            self.say(f"{first} sub-agents start in parallel: " + ", ".join(m.pick.url for m in members))
        pending, winner, verdict = set(work), None, "no sub-agent finished the task"
        try:
            while pending and winner is None:
                done, pending = await asyncio.wait(pending, return_when=asyncio.FIRST_COMPLETED)
                for task in done:
                    member = work[task]
                    if member.result is not None and member.result.status == "completed":
                        accepted, why = await self._check(member)
                        verdict = why
                        if accepted:
                            winner = member
                            break
                    elif member.found == 0 and winner is None:  # it found nothing (the site would not open, a dead end): the next pick
                        reason = member.error or (member.result.message if member.result else "") or "dead end"
                        if REFUSED.search(reason):
                            refused_hosts.add(urlsplit(member.pick.url).hostname)
                        spare[:] = [h for h in spare if urlsplit(h.url).hostname not in refused_hosts]  # a site that refused us is not asked again through another page
                        if not spare or (self.budget and self.budget.exhausted):  # nothing left to try, or nothing left to spend
                            continue
                        nxt = spare.pop(0)
                        self.say(f"{member.name} found nothing ({reason}); trying {nxt.url}")
                        replacement = start(nxt, spare=True)
                        pending.add(next(t for t, m in work.items() if m is replacement))
        finally:
            for task in pending:
                task.cancel()
            await asyncio.gather(*pending, return_exceptions=True)
            for task in pending:
                self._announce(work[task], "stopped", report="stopped: another sub-agent's result was accepted" if winner else "stopped")
        if winner is None and self.budget and self.budget.exhausted:
            verdict = f"the token budget ({self.budget.max_tokens:,}) was used up before any sub-agent finished the task"
        return TeamResult(members, winner, verdict)

    # ---- one sub-agent ----------------------------------------------------------
    def _announce(self, member: Member, status: str, **extra) -> None:
        self.rec.log(event="agent", agent=member.id, name=member.name, status=status, task=f"start from {member.pick.title}",
                     tab="own browser", url=member.pick.url, **extra)

    async def _work(self, member: Member) -> None:
        rec = self.rec.for_agent(member.id)
        store = FileStore(self.rec.files_dir, on_saved=lambda saved: rec.log(event="file", **saved.as_dict()))
        member.files = store.saved
        self._announce(member, "running")
        try:
            member.session = await self.host.session(member.pick.url, respect_robots=False, scope="web" if self.web else "site", files=store)
            if self.attach:
                await self.attach(member.session, member.id)
            agent = Agent(member.session, self.make_models(), [p.name for p in self.providers], rec,
                          max_steps=self.max_steps if not member.spare else min(self.max_steps, SPARE_STEPS), control=self.control, web=self.web,
                          search=self.search, budget=self.budget)
            start = await self._keep_if_a_file(member, rec)
            plan: TaskPlan = replace(self.brief.plan, start_url=start)
            member.result = await agent.run(self.task, plan)
            report = f"{len(member.result.rows)} items, {len(member.files)} files"
            if member.result.message:
                report += f": {member.result.message[:200]}"
            self._announce(member, "done" if member.result.status == "completed" else "failed", report=report)
        except asyncio.CancelledError:
            raise
        except Exception as error:  # one sub-agent's crash must not end the others
            member.error = f"{type(error).__name__}: {str(error)[:200]}"
            self._announce(member, "failed", report=member.error)

    async def _keep_if_a_file(self, member: Member, rec) -> str:
        """A search result that is the document itself (a PDF link) is saved at once, no browsing needed; the agent then starts on that site's home
        page and can finish, or look for more. Returns where the agent starts."""
        url = member.pick.url
        if not looks_like_file(url):
            return url
        try:
            saved = await member.session.save_file(url)
            rec.log(event="direct_file", url=url, name=saved.name, size=saved.size)
        except ActionError as error:
            rec.log(event="direct_file", url=url, error=str(error)[:200])
        parts = urlsplit(url)
        return f"{parts.scheme}://{parts.netloc}/"

    # ---- is it done? ----------------------------------------------------------------
    async def _check(self, member: Member) -> tuple[bool, str]:
        """The brain's verdict; then, unless the run is autonomous, the person's."""
        complete, why = await self._verify(member)
        self.rec.log(event="verify", agent=member.id, complete=complete, why=why)
        if not complete:
            self.say(f"{member.name}'s result was not accepted: {why}")
            return False, why
        if self.gate is None:
            return True, why
        self.rec.log(event="result_check", agent=member.id, name=member.name, items=len(member.result.rows),
                     files=[f.name for f in member.files], why=why, url=member.pick.url)
        decision = await self.gate.ask("result")
        return decision.approve, (why if decision.approve else f"the user did not accept it{': ' + decision.context if decision.context else ''}")

    async def _verify(self, member: Member) -> tuple[bool, str]:
        result = member.result
        sample = json.dumps(result.rows[:SAMPLE_ROWS], ensure_ascii=False)[:3000]
        files = ", ".join(f"{f.name} ({f.size} bytes, {f.content_type or 'unknown type'}) from {f.url}" for f in member.files) or "none"
        user = (f"TASK: {self.task}\nGOAL: {self.brief.plan.goal}\nRESULT of {member.name}, which started at {member.pick.url} and finished on {member.session.page.url if member.session else 'unknown'}"
                f" (a page that first asked for a human check may have been passed by the user since):\n"
                f"{len(result.rows)} items in total; fields: {', '.join(result.fields) or 'none'}\nsample (first {min(SAMPLE_ROWS, len(result.rows))} of {len(result.rows)}): {sample}\nfiles saved: {files}\n"
                f"its own summary: {result.message or 'none'}")
        for provider in self.providers:
            with contextlib.suppress(LLMError):
                data = (await complete_json(provider, VERIFY_SYSTEM, user)).data
                return bool(data.get("complete")), str(data.get("why") or "")[:300]
        return True, "the brain could not check it (no provider answered); the sub-agent's own check passed"
