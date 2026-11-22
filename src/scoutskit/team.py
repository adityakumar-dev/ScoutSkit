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
from .budget import Share
from .browser import ActionError, BrowserHost, BrowserSession, FileStore, looks_like_file
from .control import PlanGate, RunControl
from .provider.llm import LLMError, complete_json
from .recorder import RunRecorder
from .peek import rank as rank_by_peek
from .search import Hit, same_page

MAX_AGENTS = 3
SHARES = 3  # a sub-agent may spend at most 1/3 of the run's token budget
SPARE_STEPS = 15  # a replacement for a failed scout gets a shorter leash: the picks it falls back on are less certain
REFUSED = re.compile(r"HTTP (?:403|418|429)|block page|CAPTCHA", re.I)  # the site refused the browser: its other pages will be refused too
SAMPLE_ROWS = 5

RELEVANT_SYSTEM = """You check ONE thing: are these items the kind of thing the TASK asks for? Reply with one JSON object:
{"relevant": true or false, "why": "<one short sentence>"}
Do NOT judge which website they came from, whether the site is official, or whether the list is complete (that has been checked by counting).
Say false only if the items are clearly something else than what the task asks for (other years, other topics, navigation links, ads)."""

VERIFY_SYSTEM = """You are the main brain checking a sub-agent's result before the user gets it. Reply with one JSON object:
{"complete": true or false, "why": "<one sentence>"}
You are shown only the first few items as a sample: the item count is exact and the whole list is in the result, so never treat the sample's size as the result's size.
complete = the result fully answers the TASK: the right kind of items, all of them (compare the count with what the page states), the fields a person
would expect, or the files the task names. Part of the answer or the wrong kind of item is not complete.
The site was chosen by the plan the person approved, or named by the person: NEVER reject a result only because the site is unofficial, a mirror
or third-party (the official site may no longer list the data). Reject for the source only when it is clearly unrelated to the task.
When FACTS FROM THE PAGE give a total or a list length and the item count matches it, the extraction is complete."""


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


MAX_EXTRA_SOURCES = 4  # other search results tried after the brain's picks have all failed
MAX_FAILURES_PER_HOST = 2  # a site that two scouts could not get data from is not tried a third time


def _host(hit: Hit) -> str:
    return urlsplit(hit.url).hostname or ""


def fallback_sources(brief: Brief, picks: list[Hit]) -> list[Hit]:
    """Search results the brain did not pick, in search order: where to look when every pick has failed. Encyclopaedia articles are not data sources."""
    seen = {same_page(hit.url) for hit in picks}
    extras = []
    for hit in brief.sources:
        if same_page(hit.url) not in seen and hit.source not in ("wikipedia", "wikidata") and not hit.url.lower().endswith((".jpg", ".png", ".gif")):
            seen.add(same_page(hit.url))
            extras.append(hit)
    return extras[:MAX_EXTRA_SOURCES]


def order_spares(spares: list[Hit], failures: dict[str, int], refused: set) -> list[Hit]:
    """The sources still worth trying: not on a host that refused us or failed twice, and sites that have not failed yet before ones that have."""
    usable = [h for h in spares if _host(h) not in refused and failures.get(_host(h), 0) < MAX_FAILURES_PER_HOST]
    return sorted(usable, key=lambda h: failures.get(_host(h), 0))  # (stable: the brain's order is kept among equals)


def team_picks(brief: Brief, size: int) -> list[Hit]:
    """The sources the sub-agents start from at first."""
    return distinct_picks(brief)[: max(1, min(size, MAX_AGENTS))]


class Team:
    def __init__(
        self, host: BrowserHost, brief: Brief, task: str, *, providers: list, make_models: Callable[[], list], recorder: RunRecorder,
        max_steps: int, web: bool, control: RunControl | None = None, gate: PlanGate | None = None,
        attach: Callable[[BrowserSession, str], Awaitable[None]] | None = None, say: Callable[[str], None] = lambda _: None,
        search: Callable | None = None, budget=None, peek: bool = False,
    ) -> None:
        self.peek = peek  # look at each candidate source first (peek.py) so empty shells are not tried before real data
        self.budget = budget  # shared with every sub-agent
        self.search = search  # async (query) -> [Hit], given to every sub-agent as the web_search tool
        self.host, self.brief, self.task, self.providers, self.make_models = host, brief, task, providers, make_models
        self.rec, self.max_steps, self.web, self.control, self.gate, self.attach, self.say = recorder, max_steps, web, control, gate, attach, say

    async def run(self) -> TeamResult:
        picks = distinct_picks(self.brief)
        extras = fallback_sources(self.brief, picks)
        if self.peek and len(picks) + len(extras) > 1:
            ordered, seen = await rank_by_peek(self.host, picks + extras)
            for item in seen:
                self.rec.log(event="peek", url=item.url, items=item.items, stated=item.stated, empty=item.empty, error=item.error, rank=item.rank)
            if ordered != picks + extras:
                self.say("sources reordered after a first look: " + ", ".join(h.url for h in ordered[:3]))
            picks, extras = ordered[: len(picks)], ordered[len(picks):]
            if not picks:
                picks = ordered
        first = max(1, min(self.brief.agents, MAX_AGENTS, len(picks)))
        spare = picks[first:] + extras  # sources nobody started from: tried one by one when a sub-agent does not deliver
        failures: dict[str, int] = {}
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
                    reason = member.error or (member.result.message if member.result else "") or "dead end"
                    if member.result is not None and member.result.status == "completed":
                        accepted, why = await self._check(member)
                        verdict = why
                        if accepted:
                            winner = member
                            break
                        reason = f"its result was not accepted: {why}"
                    # it did not deliver (the site would not open, a dead end, a result that was turned down): the next source takes over, whatever
                    # it picked up on the way (a file, a few rows); the best of what was found is still the answer if nothing better turns up
                    if REFUSED.search(reason):
                        refused_hosts.add(urlsplit(member.pick.url).hostname)
                    failures[_host(member.pick)] = failures.get(_host(member.pick), 0) + 1
                    spare[:] = order_spares(spare, failures, refused_hosts)  # not a site that refused us or failed twice; fresh sites first
                    broke = bool(self.budget and self.budget.exhausted)
                    self.rec.log(event="failover", agent=member.id, reason=reason[:160], spare_left=len(spare), budget_spent=self.budget.spent if self.budget else 0,
                                 budget_exhausted=broke)
                    if not spare or broke:  # nothing left to try, or nothing left to spend
                        continue
                    nxt = spare.pop(0)
                    self.say(f"{member.name} did not deliver ({reason}); trying {nxt.url}")
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
                          search=self.search, budget=self._share())
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

    def _share(self):
        """Each sub-agent may use a third of the run's budget: one that cannot find its data must not leave nothing for the next source."""
        if self.budget is None or self.budget.max_tokens <= 0:
            return self.budget
        return Share(self.budget, self.budget.max_tokens // SHARES)

    # ---- is it done? ----------------------------------------------------------------
    async def _check(self, member: Member) -> tuple[bool, str]:
        """The brain's verdict; then, unless the run is autonomous, the person's."""
        complete, why = await self._verify(member)
        self.rec.log(event="verify", agent=member.id, complete=complete, why=why)
        if not complete and self.gate is None:  # autonomous: the brain decides
            self.say(f"{member.name}'s result was not accepted: {why}")
            return False, why
        if self.gate is None:
            return True, why
        # with a person in the loop the brain advises and the person decides: a result the brain doubts is shown with its doubt
        has_something = bool(member.result.rows or member.files)
        if not complete and not has_something:
            self.say(f"{member.name}'s result was not accepted: {why}")
            return False, why
        self.rec.log(event="result_check", agent=member.id, name=member.name, items=len(member.result.rows), doubt=not complete,
                     files=[f.name for f in member.files], why=why, url=member.pick.url)
        decision = await self.gate.ask("result")
        return decision.approve, (why if decision.approve else f"the user did not accept it{': ' + decision.context if decision.context else ''}")

    async def _relevant(self, member: Member, counted: str) -> tuple[bool, str]:
        """The narrow question: are these the kind of items the task asks for? Not the site, not completeness (counting settled that)."""
        result = member.result
        user = (f"TASK: {self.task}\nSAMPLE of {len(result.rows)} items (fields: {', '.join(result.fields)}): "
                f"{json.dumps(result.rows[:SAMPLE_ROWS], ensure_ascii=False)[:2500]}")
        for provider in self.providers:
            with contextlib.suppress(LLMError):
                data = (await complete_json(provider, RELEVANT_SYSTEM, user)).data
                ok = bool(data.get("relevant"))
                return ok, (f"{counted}; " + str(data.get("why") or "")[:200]) if ok else str(data.get("why") or "these are not the items the task asks for")[:300]
        return True, f"{counted}; the brain could not check relevance (no provider answered)"

    async def _page_numbers(self, member: Member) -> tuple[int | None, int | None]:
        """(the total the page states, how many items its list holds): what a result can be counted against. Advice only: never raises."""
        if member.session is None:
            return None, None
        try:
            total = await member.session.stated_total()
            found = await member.session.repeats()
            return total, (found.live if found and found.live >= 5 else None)
        except Exception:
            return None, None

    async def _page_facts(self, member: Member) -> str:
        """What the page itself says about its list (a stated total, how many items it holds), so completeness can be judged, not guessed."""
        if member.session is None:
            return ""
        parts = []
        try:
            total = await member.session.stated_total()
            if total:
                parts.append(f"the page states a total of {total}")
            found = await member.session.repeats()
            if found and found.live >= 5:
                parts.append(f"the page's list holds {found.live} items")
        except Exception:  # advice only
            return ""
        return "\nFACTS FROM THE PAGE THE RESULT CAME FROM: " + "; ".join(parts) if parts else ""

    async def _verify(self, member: Member) -> tuple[bool, str]:
        result = member.result
        total, listed = await self._page_numbers(member)
        count = len(result.rows)
        if count >= 5 and count in (total, listed):
            # The page itself says how many there are and the result has exactly that many: completeness is settled by counting, not by opinion.
            # What is left to judge is only whether these are the kind of items the task asks for.
            return await self._relevant(member, f"the result has {count} items, exactly the {'total the page states' if count == total else 'length of the page list'}")
        sample = json.dumps(result.rows[:SAMPLE_ROWS], ensure_ascii=False)[:3000]
        files = ", ".join(f"{f.name} ({f.size} bytes, {f.content_type or 'unknown type'}) from {f.url}" for f in member.files) or "none"
        facts = await self._page_facts(member)
        user = (f"TASK: {self.task}\nGOAL: {self.brief.plan.goal}{facts}\nRESULT of {member.name}, which started at {member.pick.url} and finished on {member.session.page.url if member.session else 'unknown'}"
                f" (a page that first asked for a human check may have been passed by the user since):\n"
                f"{len(result.rows)} items in total; fields: {', '.join(result.fields) or 'none'}\nsample (first {min(SAMPLE_ROWS, len(result.rows))} of {len(result.rows)}): {sample}\nfiles saved: {files}\n"
                f"its own summary: {result.message or 'none'}")
        for provider in self.providers:
            with contextlib.suppress(LLMError):
                data = (await complete_json(provider, VERIFY_SYSTEM, user)).data
                return bool(data.get("complete")), str(data.get("why") or "")[:300]
        return True, "the brain could not check it (no provider answered); the sub-agent's own check passed"
