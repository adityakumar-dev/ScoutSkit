"""A quick look at each candidate source before any scout starts: does the page hold a list, or does it say it has no data?

No model is involved: the page is loaded in its own browser context and measured (the finder of repeated items, the total the page
states, the "no data" wording). A source that is an empty shell, like an official page whose table says "No data available", goes to the
back of the queue; a source that holds a real list goes to the front. Costs a few seconds and no tokens.
"""

from __future__ import annotations

import asyncio
import contextlib
from dataclasses import dataclass

from .agent import NO_DATA
from .browser import ActionError, BrowserHost
from .search import Hit

PEEK_TIMEOUT_S = 25
MAX_PEEKS = 6
LIST_MIN = 5


@dataclass(frozen=True)
class Peek:
    url: str
    items: int = 0  # repeated items found on the page
    stated: int | None = None  # a total the page states about its list
    empty: bool = False  # the page says it holds no data
    error: str = ""  # could not be loaded (refused, slow, broken)

    @property
    def rank(self) -> int:
        """0: holds a list. 1: unknown (could not look, or nothing to go on). 2: says it has no data."""
        if self.items >= LIST_MIN:
            return 0
        if self.empty or self.stated == 0:
            return 2
        return 1


    @property
    def order(self) -> tuple[int, int]:
        """Rank first; among pages with a list, one whose length equals the total it states (the real data) before one that only repeats something."""
        return self.rank, 0 if self.items >= LIST_MIN and self.stated == self.items else 1


async def peek(host: BrowserHost, hit: Hit) -> Peek:
    session = None
    try:
        session = await host.session(hit.url, respect_robots=False, scope="web")
        async with asyncio.timeout(PEEK_TIMEOUT_S):
            await session.goto(hit.url)
            tree, _ = await session.snapshot(full=False)
            found = await session.repeats()
            stated = await session.stated_total()
        return Peek(hit.url, items=found.live if found else 0, stated=stated, empty=bool(NO_DATA.search(tree)) and not found)
    except (ActionError, TimeoutError, asyncio.TimeoutError) as error:
        return Peek(hit.url, error=str(error)[:120] or type(error).__name__)
    except Exception as error:  # a page that breaks the browser says nothing about the others
        return Peek(hit.url, error=f"{type(error).__name__}: {str(error)[:100]}")
    finally:
        if session is not None:
            with contextlib.suppress(Exception):
                await session.context.close()


async def rank(host: BrowserHost, hits: list[Hit]) -> tuple[list[Hit], list[Peek]]:
    """The hits with the ones that hold data first and the empty ones last (the original order is kept among equals), and what was seen."""
    sample = hits[:MAX_PEEKS]
    seen = await asyncio.gather(*(peek(host, hit) for hit in sample))
    by_url = {p.url: p for p in seen}
    ordered = sorted(sample, key=lambda hit: by_url[hit.url].order) + hits[MAX_PEEKS:]
    return ordered, list(seen)
