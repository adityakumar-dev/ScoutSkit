"""What every search source returns, and running several at once.

A source that fails (rate-limited, offline, refused) never stops the others: its failure becomes a note the user sees.
"""

from __future__ import annotations

import asyncio
from dataclasses import asdict, dataclass
from typing import Protocol
from urllib.parse import urlsplit, urlunsplit

MAX_SNIPPET = 300
SOURCE_TIMEOUT_S = 20


@dataclass(frozen=True)
class Hit:
    title: str
    url: str
    snippet: str
    source: str  # which search source found it, e.g. "duckduckgo", "wikidata"

    def as_dict(self) -> dict:
        return asdict(self)


class SearchSource(Protocol):
    name: str

    async def search(self, query: str, limit: int) -> list[Hit]: ...


def same_page(url: str) -> str:
    """A key under which the same page found twice (www., trailing slash, #part) counts once."""
    parts = urlsplit(url.strip())
    host = parts.netloc.lower().removeprefix("www.")
    return urlunsplit(("https" if parts.scheme in ("http", "https") else parts.scheme, host, parts.path.rstrip("/"), parts.query, ""))


SEARCH_ENGINES = {"duckduckgo", "google", "bing", "yahoo", "yandex", "brave", "baidu", "ecosia"}
SECOND_LEVEL = {"co", "com", "org", "net"}  # google.co.in, bing.com.au


def is_search_page(url: str) -> bool:
    """A results page of a search engine. These refuse automated browsers (a block page or a CAPTCHA), so the agent uses web_search instead."""
    parts = urlsplit(url)
    labels = (parts.hostname or "").lower().split(".")
    if len(labels) < 2:
        return False
    name = labels[-3] if len(labels) >= 3 and labels[-2] in SECOND_LEVEL else labels[-2]
    return name in SEARCH_ENGINES and parts.path.rstrip("/") in ("", "/search", "/html", "/web") and any(k in parts.query for k in ("q=", "p=", "text="))


def clean(text: str, limit: int = MAX_SNIPPET) -> str:
    text = " ".join(str(text or "").split())
    return text if len(text) <= limit else text[: limit - 1] + "…"


async def gather(sources: list[SearchSource], queries: list[str], *, per_query: int = 8, limit: int = 20) -> tuple[list[Hit], list[str]]:
    """Every source on every query in parallel. Returns the hits (first sighting wins, in query order) and notes on failures."""
    jobs = [(source, query) for query in queries for source in sources]

    async def one(source: SearchSource, query: str) -> list[Hit]:
        return await asyncio.wait_for(source.search(query, per_query), SOURCE_TIMEOUT_S)

    results = await asyncio.gather(*(one(s, q) for s, q in jobs), return_exceptions=True)
    hits: dict[str, Hit] = {}
    notes: list[str] = []
    for (source, query), result in zip(jobs, results):
        if isinstance(result, BaseException):
            reason = "timed out" if isinstance(result, asyncio.TimeoutError) else f"{type(result).__name__}: {clean(str(result), 120)}"
            notes.append(f"{source.name} gave nothing for {query!r} ({reason})")
            continue
        for hit in result:
            if hit.url.startswith(("http://", "https://")):
                hits.setdefault(same_page(hit.url), hit)
    return list(hits.values())[:limit], notes
