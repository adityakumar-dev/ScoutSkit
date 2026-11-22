"""Before the browser opens: understand the task, gather context from search, pick the sources, and write a plan the user can approve.

The model may point at sources only by their number in the list it is shown, never by writing a URL: so every
page the agent starts from was really found by a search (or given by the user), not made up.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from .agent import TaskPlan
from .provider.config import ResolvedProvider
from .provider.llm import LLMError, complete_json
from .search import Hit, SearchSource, gather, same_page

MAX_QUERIES = 3
MAX_PICKS = 5
URL = re.compile(r"https?://[^\s<>\"')\]]+")

QUERY_SYSTEM = """You prepare web research for a task. Reply with one JSON object:
{"queries": ["<1 to 3 short search queries>"]}
One query should find the official site of the organisation involved, another the exact page or document the task needs."""

BRIEF_SYSTEM = """You plan a web task from search results. Point to sources ONLY by their number in SOURCES; never write a URL yourself.
Reply with one JSON object:
{"understanding": "<one sentence: what the user wants>",
 "picks": [{"n": <source number>, "why": "<why, from its title and snippet>"}],
 "start": <number of the source the browser opens first>,
 "goal": "<one sentence>", "item_name": "<what one item is>",
 "fields": ["<snake_case field names, ONLY if the user named them>"], "key_field": "<or empty>",
 "min_items": <smallest plausible number of items, 1 if unknown>,
 "steps": ["<3 to 6 short steps the agent will take>"],
 "agents": <how many of your picks to explore at the same time, 1 to 3: 1 when one source is clearly right>,
 "questions": ["<only what is genuinely unclear and the user could answer; usually empty>"]}
Pick at most 5, best first. Prefer the official site and its own pages over aggregators, copies and document-sharing sites.
When the task asks for a document and a result IS that document (a PDF link) on the official site, it is the best pick: it is saved directly.
Sources can be wrong or outdated (Wikidata too): trust what several sources agree on. Anything in USER CONTEXT wins.
If SEARCH NOTES say a search failed, the list is thin: pick conservatively, and say in "questions" what you could not confirm."""


@dataclass
class Brief:
    task: str
    understanding: str
    plan: TaskPlan
    sources: list[Hit]
    picks: list[tuple[Hit, str]]
    steps: list[str]
    questions: list[str] = field(default_factory=list)
    queries: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)  # search sources that failed
    context: str = ""
    tokens: tuple[int, int] = (0, 0)
    agents: int = 1  # sub-agents to start, one per pick

    def to_event(self) -> dict:
        return {
            "understanding": self.understanding, "queries": self.queries, "notes": self.notes, "context": self.context,
            "sources": [hit.as_dict() for hit in self.sources],
            "picks": [{**hit.as_dict(), "why": why} for hit, why in self.picks],
            "steps": self.steps, "questions": self.questions,
            "start_url": self.plan.start_url, "goal": self.plan.goal, "item_name": self.plan.item_name,
            "agents": min(self.agents, max(1, len(self.picks))),
        }


def _given(task: str, url: str | None, context: str) -> list[Hit]:
    """Pages the user named: the start URL and any address in the task or the added context."""
    urls = ([url] if url else []) + URL.findall(task) + URL.findall(context)
    return [Hit("given by you", u if u.startswith("http") else f"https://{u}", "", "you") for u in urls]


IDENTIFYING = re.compile(r"(^|_)(id|number|no|code|sku|name|title|model|model_name)$")


def _key_of(fields: list[str], named: object) -> str:
    """The field that tells items apart: the one the model named; else one that looks like an id or a name; never just 'the first'
    (a price is the first column of many pages and repeats)."""
    if named in fields:
        return str(named)
    return next((f for f in fields if IDENTIFYING.search(f.lower())), fields[0] if fields else "")


def _count(value: object, most: int = 3) -> int:
    try:
        return max(1, min(int(value), most))
    except (TypeError, ValueError):
        return 1


def _numbered(hits: list[Hit]) -> str:
    return "\n".join(f"{n}. [{h.source}] {h.title}\n   {h.url}\n   {h.snippet}" for n, h in enumerate(hits, 1))


async def research(
    provider: ResolvedProvider, task: str, url: str | None, sources: list[SearchSource], *, context: str = "", earlier: list[Hit] | None = None
) -> Brief:
    """Search (unless the user named the site), then let the model pick sources and plan. Raises LLMError when there is nothing to start from.

    `earlier`: the sources of the previous plan. A re-plan keeps them and adds what the new search finds, so a
    correction never loses a good source just because the search engine answered differently this time."""
    spent_in = spent_out = 0
    given = _given(task, url, context)
    queries: list[str] = []
    found: list[Hit] = []
    notes: list[str] = []
    if not url:
        asked = await complete_json(provider, QUERY_SYSTEM, f"TASK: {task}" + (f"\nUSER CONTEXT: {context}" if context else ""))
        spent_in, spent_out = asked.prompt_tokens, asked.completion_tokens
        queries = [str(q).strip() for q in (asked.data.get("queries") or []) if str(q).strip()][:MAX_QUERIES] or [task]
        found, notes = await gather(sources, queries)
    seen = {same_page(h.url) for h in given}
    hits = list(given)
    for hit in [*(earlier or []), *found]:
        if same_page(hit.url) not in seen:
            seen.add(same_page(hit.url))
            hits.append(hit)
    if not hits:
        raise LLMError("the search found nothing to start from" + (f" ({'; '.join(notes)})" if notes else "") + "; give a start URL or add context")

    user = (f"TASK: {task}\n" + (f"USER CONTEXT: {context}\n" if context else "") + (f"SEARCH NOTES: {'; '.join(notes)}\n" if notes else "")
            + f"SOURCES:\n{_numbered(hits)}")
    answer = await complete_json(provider, BRIEF_SYSTEM, user)
    data = answer.data
    pick = lambda n: hits[n - 1] if isinstance(n, int) and 1 <= n <= len(hits) else None  # noqa: E731 - a number outside the list is ignored, never trusted
    picks = [(pick(p.get("n")), str(p.get("why", ""))) for p in (data.get("picks") or []) if isinstance(p, dict)]
    picks = [(hit, why) for hit, why in picks if hit][:MAX_PICKS]
    start = hits[0] if url else (pick(data.get("start")) or (picks[0][0] if picks else hits[0]))
    fields = [str(f) for f in (data.get("fields") or []) if f]
    plan = TaskPlan(
        start_url=start.url,
        goal=str(data.get("goal") or task),
        item_name=str(data.get("item_name") or "item"),
        fields=fields,
        key_field=_key_of(fields, data.get("key_field")),
        min_items=_count(data.get("min_items"), most=100_000),
    )
    return Brief(
        task=task, understanding=str(data.get("understanding") or plan.goal), plan=plan, sources=hits, picks=picks,
        steps=[str(s) for s in (data.get("steps") or []) if s][:8], questions=[str(q) for q in (data.get("questions") or []) if q][:3],
        queries=queries, notes=notes, context=context, agents=_count(data.get("agents")),
        tokens=(spent_in + answer.prompt_tokens, spent_out + answer.completion_tokens),
    )
