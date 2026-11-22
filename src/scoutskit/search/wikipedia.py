"""Wikipedia's official search API, plus each article's official website from Wikidata (property P856).

The official website is the most useful thing here: it tells the planner which site is the real one, instead of the model guessing.
"""

from __future__ import annotations

import re

import httpx

from .base import Hit, clean

API = "https://en.wikipedia.org/w/api.php"
WIKIDATA = "https://www.wikidata.org/w/api.php"
HEADERS = {"User-Agent": "ScoutsKit/0.1 (research agent; local use)"}  # Wikimedia asks automated clients to name themselves
ARTICLES = 3  # official websites are looked up for the top few articles only


class Wikipedia:
    name = "wikipedia"

    def __init__(self, client: httpx.AsyncClient | None = None) -> None:
        self._client = client

    async def search(self, query: str, limit: int) -> list[Hit]:
        http = self._client or httpx.AsyncClient(timeout=15, headers=HEADERS)
        try:
            found = (await http.get(API, params={"action": "query", "list": "search", "srsearch": query, "srlimit": min(limit, ARTICLES),
                                                 "format": "json", "formatversion": 2})).json()["query"]["search"]
            if not found:
                return []
            titles = [page["title"] for page in found]
            sites = await self._official_sites(http, titles)
            hits = []
            for page in found:
                snippet = clean(re.sub(r"<[^>]+>", "", page.get("snippet", "")))
                if page["title"] in sites:
                    hits.append(Hit(f"{page['title']} — official website", sites[page["title"]], f"Wikidata lists this as the official website (it can be out of date). {snippet}", "wikidata"))
                hits.append(Hit(f"{page['title']} — Wikipedia", f"https://en.wikipedia.org/wiki/{page['title'].replace(' ', '_')}", snippet, self.name))
            return hits
        finally:
            if self._client is None:
                await http.aclose()

    async def _official_sites(self, http: httpx.AsyncClient, titles: list[str]) -> dict[str, str]:
        pages = (await http.get(API, params={"action": "query", "prop": "pageprops", "titles": "|".join(titles), "format": "json",
                                             "formatversion": 2})).json()["query"]["pages"]
        items = {p["pageprops"]["wikibase_item"]: p["title"] for p in pages if p.get("pageprops", {}).get("wikibase_item")}
        if not items:
            return {}
        entities = (await http.get(WIKIDATA, params={"action": "wbgetentities", "ids": "|".join(items), "props": "claims", "format": "json"})).json()["entities"]
        sites = {}
        for qid, entity in entities.items():
            for claim in entity.get("claims", {}).get("P856", [])[:1]:
                value = claim.get("mainsnak", {}).get("datavalue", {}).get("value")
                if isinstance(value, str) and value.startswith("http"):
                    sites[items[qid]] = value
        return sites
