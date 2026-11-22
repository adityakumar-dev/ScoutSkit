"""web_search: real search results as data, so the browser never has to open a search engine (which refuses automated browsers)."""

from __future__ import annotations

from ..browser import ActionError
from .context import ToolContext
from .registry import Tool, ToolRegistry

MAX_RESULTS = 8


def register(registry: ToolRegistry, ctx: ToolContext) -> None:
    if ctx.search is None:
        return

    async def web_search(query: str) -> str:
        hits = (await ctx.search(str(query)))[:MAX_RESULTS]
        if not hits:
            raise ActionError(f"the search found nothing for {query!r}; try other words")
        lines = [f"{n}. [{h.source}] {h.title}\n   {h.url}\n   {h.snippet}" for n, h in enumerate(hits, 1)]
        return "\n".join(lines) + "\n(these are search results, not pages you have seen: open one with open_tab/goto, or keep a document with save_file(its link))"

    registry.register(Tool(
        "web_search", "Search the web (DuckDuckGo, Wikipedia) and get titles, links and snippets as text. Use it to find a site or a document; "
        "never open a search engine in the browser.", {"query": "what to search for"}, web_search, reads=True,
    ))
