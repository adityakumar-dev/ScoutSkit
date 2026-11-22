"""Free web search through the `ddgs` library (no key).

There is no official free search API behind this: ddgs reads the search engines' own result pages, one after another. It is free,
but an engine may rate-limit it. A failed attempt is retried a few times; if all fail, that is reported as a note and the other sources carry on.
"""

from __future__ import annotations

import asyncio

from .base import Hit, clean


RETRIES = 3  # ddgs tries one search engine after another and fails now and then ("No results found") although a second try works
RETRY_WAIT_S = 1.0


class WebSearch:
    """Free web search through ddgs. ddgs is a metasearch library: it asks DuckDuckGo, Bing, Brave, Yahoo and others in turn, so the
    results are labelled "web", not with one engine's name."""

    name = "web"

    async def search(self, query: str, limit: int) -> list[Hit]:
        from ddgs import DDGS  # imported here: the library is only needed when this source is used

        rows: list[dict] = []
        for attempt in range(RETRIES):
            try:
                rows = await asyncio.to_thread(lambda: DDGS().text(query, max_results=limit) or [])
            except Exception as error:  # ddgs raises its own exception type for "no results" and for rate limits
                if attempt == RETRIES - 1:
                    raise
                await asyncio.sleep(RETRY_WAIT_S * (attempt + 1))
                continue
            if rows:
                break
        return [Hit(clean(r.get("title", ""), 160), str(r.get("href", "")), clean(r.get("body", "")), self.name) for r in rows]


DuckDuckGo = WebSearch  # the name the configuration used before
