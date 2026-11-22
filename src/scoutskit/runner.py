"""One task, start to finish: pick a provider, plan, run the agent in a browser, save the evidence and a recipe.

The CLI and the server both call execute(); they differ only in where they show progress (`say`)
and in what they attach to the run (`attach`: the server hooks the live view and the event stream there).
"""

from __future__ import annotations

import inspect
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path

from .browser import BrowserSession
from .control import PlanGate, RunControl
from .provider import ConfigError, ensure_providers, load_settings, resolve_provider
from .recorder import RunRecorder

Say = Callable[[str], None]
Attach = Callable[..., Awaitable[None] | None]  # told about each session as it opens: (session, agent id)


@dataclass
class Outcome:
    status: str
    items: int
    steps: int
    message: str
    run_dir: Path
    recipe_saved: bool
    summary: dict


async def choose_providers(provider_name: str | None, strict: bool, say: Say) -> list:
    settings = load_settings()
    names, note = await ensure_providers(settings, provider_name)
    if strict:
        if not provider_name:
            raise ConfigError("--strict needs --provider")
        if provider_name not in names:
            raise ConfigError(f"{provider_name!r} is not usable right now; run `scoutskit providers --check`")
        names, note = [provider_name], None
    if not names:
        raise ConfigError("No working LLM provider. Run `scoutskit providers --check` to see why each one failed.")
    if note:
        say(note)
    return [resolve_provider(settings, name) for name in names]


async def _first_working(providers: list, attempt: Callable, say: Say):
    """attempt(provider) with each provider in turn until one works; the last failure is raised."""
    from .provider.llm import LLMError

    for index, provider in enumerate(providers):
        try:
            return await attempt(provider)
        except LLMError as error:
            if index == len(providers) - 1:
                raise
            say(f"planning with {provider.name} failed ({error}); trying {providers[index + 1].name}")
    raise LLMError("no provider to plan with")


async def execute(
    task: str, *, url: str | None = None, provider_name: str | None = None, max_steps: int | None = None,
    headed: bool = False, strict: bool = False, web: bool = False, say: Say = lambda _: None, attach: Attach | None = None,
    recorder: RunRecorder | None = None, control: RunControl | None = None, gate: PlanGate | None = None,
) -> Outcome:
    """`gate`: when given, the plan waits there for the person's approval (or their added context); without it the plan is followed at once."""
    from .brief import research
    from .browser import open_browser
    from .search import make_sources
    from .team import Team
    from .provider.chat import make_chat_model
    from .recipe import RECIPE_FILE, find_feed, from_run

    settings = load_settings()
    recorder = recorder or RunRecorder(settings.runs_dir)  # made first, so even a run that fails while planning leaves evidence
    recorder.log(event="task", task=task)  # so a run that never gets a plan still shows what it was asked
    providers = await choose_providers(provider_name, strict, say)
    say(f"providers (in fallback order): {', '.join(p.name for p in providers)}")

    sources = make_sources(settings.agent.search_sources)
    context, earlier = "", None
    while True:
        brief = await _first_working(providers, lambda p: research(p, task, url, sources, context=context, earlier=earlier), say)
        recorder.log(event="brief", **brief.to_event())
        if gate is None:
            break
        decision = await gate.ask()
        if decision.approve:
            break
        context, earlier = f"{context}\n{decision.context}".strip(), brief.sources
        say("re-planning with your context")
    plan, (plan_in, plan_out) = brief.plan, brief.tokens
    recorder.log(event="plan", goal=plan.goal, start_url=plan.start_url, item_name=plan.item_name, fields=plan.fields, min_items=plan.min_items)
    recorder.log(event="todo", items=[{"text": step, "status": "todo"} for step in brief.steps])
    say(f"plan: open {plan.start_url} and collect {plan.item_name}s with {plan.fields or 'the page columns'} (key: {plan.key_field or 'auto'})")

    from urllib.parse import urlsplit

    from .budget import Budget
    from .team import team_picks

    hosts = {urlsplit(hit.url).hostname for hit in team_picks(brief, brief.agents)}  # the sites the first sub-agents start from
    if len(hosts) > 1 and not web:  # a plan that names several sites needs to visit them; the person approved it
        web = True
        say(f"the plan starts on {len(hosts)} sites ({', '.join(sorted(h for h in hosts if h)[:4])}): sub-agents may visit public websites")
    async with open_browser(headless=settings.agent.headless and not headed) as host:
        team = Team(host, brief, task, providers=providers, make_models=lambda: [make_chat_model(p) for p in providers], recorder=recorder,
                    max_steps=max_steps or settings.agent.max_steps, web=web, control=control, gate=gate, attach=_attacher(attach), say=say,
                    search=_searcher(sources), budget=Budget(settings.agent.team_token_budget))
        outcome = await team.run()
        best = outcome.best
        result = best.result
        rows, fields = (result.rows, result.fields) if result else ([], [])
        status = _status(outcome)
        feed = await find_feed(best.session, rows, fields) if status == "completed" and best.session and rows else None

    message = outcome.verdict if outcome.winner or not result else (result.message or outcome.verdict)
    steps = sum(m.result.steps for m in outcome.members if m.result)
    tokens_in = plan_in + sum(m.result.prompt_tokens for m in outcome.members if m.result)
    tokens_out = plan_out + sum(m.result.completion_tokens for m in outcome.members if m.result)
    summary = {
        "task": task, "status": status, "steps": steps, "items": len(rows), "files": [f.name for m in outcome.members for f in m.files],
        "agents": len(outcome.members), "winner": outcome.winner.id if outcome.winner else None,
        "provider": [p.model_name for p in providers], "message": message,
        "tokens": {"prompt": tokens_in, "completion": tokens_out},
    }
    recorder.save_result(rows, fields, summary)
    saved = False
    if status == "completed":
        recipe = from_run(recorder.dir, feed, agent=best.id)
        if recipe:
            recipe.save(recorder.dir / RECIPE_FILE)
            saved = True
            say(f"recipe saved: {recorder.dir / RECIPE_FILE} ({len(recipe.steps)} steps, {'repeats the extraction' if recipe.extracts else 'actions only'})")
    return Outcome(status, len(rows), steps, message, recorder.dir, saved, summary)


def _searcher(sources):
    """The web_search tool's engine: every configured source on one query, merged; failures are skipped."""
    from .search import gather

    async def search(query: str) -> list:
        hits, _ = await gather(sources, [query])
        return hits
    return search


def _status(outcome) -> str:
    """completed only for an accepted result; a result the brain or the person turned down is incomplete."""
    if outcome.winner:
        return "completed"
    result = outcome.best.result
    if result is None:
        return "failed"
    return "incomplete" if result.status == "completed" else result.status


def _attacher(attach: Attach | None):
    """The server's hook takes (session, agent); an older one-argument hook is told about the first session only."""
    if attach is None:
        return None
    takes_agent = len(inspect.signature(attach).parameters) >= 2
    told = False

    async def hook(session, agent: str) -> None:
        nonlocal told
        if not takes_agent and told:
            return
        told = True
        attached = attach(session, agent) if takes_agent else attach(session)
        if inspect.isawaitable(attached):
            await attached

    return hook
