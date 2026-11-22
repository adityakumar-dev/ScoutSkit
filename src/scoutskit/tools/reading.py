"""Tools that only read: page text, the page's requests and console, and slices of its HTML source."""

from __future__ import annotations

import re

from ..browser import ActionError
from .context import ToolContext
from .registry import Tool, ToolRegistry

SOURCE_WINDOW = 40  # lines per view_source call: a slice, never the whole file
GREP_SHOWN = 5  # matches shown by grep_source, the rest are only counted


def register(registry: ToolRegistry, ctx: ToolContext) -> None:
    session = ctx.session

    async def read_page(ref: str | None = None, full: bool = False) -> str:
        return await session.read_page(ref, bool(full))

    async def inspect_element(ref: str) -> str:
        return await session.element_info(str(ref))

    async def find(query: str, limit: int = 15) -> str:
        return await session.find(str(query), int(limit))

    async def javascript_tool(expression: str) -> str:
        return await session.evaluate(str(expression))

    async def page_text(max_chars: int = 6000) -> str:
        return await session.text(int(max_chars))

    async def network_log(pattern: str | None = None) -> str:
        entries = session.network_log(pattern)
        return "\n".join(e.line() for e in entries) or "no matching requests"

    async def network_body(index: int) -> str:
        return await session.network_body(int(index))

    async def console_log(errors_only: bool = False) -> str:
        return "\n".join(session.console_log(bool(errors_only))) or "console is empty"

    async def _source(which: str) -> tuple[str, str]:
        if which not in ("raw", "rendered"):
            raise ActionError("source must be 'raw' or 'rendered'")
        return await session.source_html(which)

    async def view_source(start: int = 1, end: int | None = None, source: str = "raw") -> str:
        text, note = await _source(source)
        lines = text.splitlines()
        first = max(1, int(start))
        if first > len(lines):
            return f"the {source} source has only {len(lines):,} lines"
        last = min(len(lines), first + SOURCE_WINDOW - 1, int(end) if end else first + SOURCE_WINDOW - 1)
        body = "\n".join(f"{n}: {lines[n - 1][:220]}{'…' if len(lines[n - 1]) > 220 else ''}" for n in range(first, last + 1))
        return f"[{source} source: {len(lines):,} lines, {len(text):,} chars; showing {first}-{last}]" + (f" {note}" if note else "") + "\n" + body

    async def grep_source(pattern: str, context: int = 1, source: str = "raw") -> str:
        text, note = await _source(source)
        try:
            rx = re.compile(pattern, re.IGNORECASE)
        except re.error as error:
            raise ActionError(f"bad regex: {error}") from error
        lines = text.splitlines()
        hits = [i for i, line in enumerate(lines) if rx.search(line)]
        out = [f"{len(hits)} matching lines in the {source} source ({len(lines):,} lines)" + (f"; {note}" if note else "")]
        for i in hits[:GREP_SHOWN]:
            lo, hi = max(0, i - int(context)), min(len(lines), i + int(context) + 1)
            out.append(f"--- line {i + 1}")
            out += [f"{n + 1}: {lines[n][:200]}" for n in range(lo, hi)]
        if len(hits) > GREP_SHOWN:
            out.append(f"... {len(hits) - GREP_SHOWN} more matching lines; the last is line {hits[-1] + 1}")
        return "\n".join(out)

    for tool in (
        Tool("read_page", "Read the page tree again, or only the part under one element (pass its ref). Long runs of identical items are folded "
             "into one '… N more … items' line; full=true unfolds everything (use sparingly: it is large).",
             {"ref": "element whose part to read?", "full": "true to unfold repeated items?"}, read_page, reads=True),
        Tool("inspect_element", "Show the REAL HTML behind a tree element: tag, id, classes, a CSS selector and what it contains. The tree's role names "
             "(grid, rowgroup, gridcell...) are not HTML tags; use this before writing selectors for run_python or javascript_tool.",
             {"ref": "the element's ref"}, inspect_element, reads=True),
        Tool("find", "Search the whole page tree (including rows folded away) for elements whose line contains every word; interactive elements first.",
             {"query": "words to look for, e.g. 'next page' or 'R150'", "limit": "most results to return?"}, find, reads=True),
        Tool("javascript_tool", "Read data from the page with JavaScript: an expression (or statements ending in `return value`) whose value comes back as JSON. "
             "Read-only: code that uses the network, navigates or changes the page is refused.",
             {"expression": "e.g. document.querySelectorAll('tr').length"}, javascript_tool, reads=True),
        Tool("page_text", "Read the visible text of the page.", {"max_chars": "limit?"}, page_text, reads=True),
        Tool("network_log", "List the requests the page made (find JSON/data calls).", {"pattern": "regex on the URL?"}, network_log, reads=True),
        Tool("network_body", "Read the response body of a request from network_log.", {"index": "the # number"}, network_body, reads=True),
        Tool("console_log", "Read the browser console.", {"errors_only": "true to show only errors?"}, console_log, reads=True),
        Tool("view_source", "Show a few lines of the page's HTML source (at most 40 per call; never read it all). raw = as the server sent it "
             "(includes rows that a script later hides), rendered = the live DOM.",
             {"start": "first line number", "end": "last line number?", "source": "raw or rendered?"}, view_source, reads=True),
        Tool("grep_source", "Search the page's HTML source with a regex: returns how many lines match and the first few with context. "
             "Use it to find the repeating structure of the data.",
             {"pattern": "regex, case-insensitive", "context": "lines of context?", "source": "raw or rendered?"}, grep_source, reads=True),
    ):
        registry.register(tool)
