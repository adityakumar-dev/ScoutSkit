"""Finding where to look before opening a browser: free search sources, run together, merged."""

from .base import Hit, SearchSource, gather, is_search_page, same_page
from .duckduckgo import DuckDuckGo, WebSearch
from .wikipedia import Wikipedia

SOURCES = {"web": WebSearch, "duckduckgo": WebSearch, "wikipedia": Wikipedia}  # "duckduckgo": the old name of "web"
DEFAULT_SOURCES = ("web", "wikipedia")


def make_sources(names) -> list[SearchSource]:
    unknown = [n for n in names if n not in SOURCES]
    if unknown:
        raise ValueError(f"unknown search source(s) {', '.join(unknown)}; choose from {', '.join(SOURCES)}")
    return [SOURCES[name]() for name in names]


__all__ = ["DEFAULT_SOURCES", "SOURCES", "DuckDuckGo", "WebSearch", "Hit", "SearchSource", "Wikipedia", "gather", "is_search_page", "make_sources", "same_page"]
