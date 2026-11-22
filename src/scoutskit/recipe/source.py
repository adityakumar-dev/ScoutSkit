"""Find the request a run's data really came from, so replay can read it again instead of repeating clicks."""

from __future__ import annotations

from urllib.parse import urlparse

from ..browser import BrowserSession
from ..browser.feeds import records_in
from .model import Feed

MATCH_SHARE = 0.9  # of the collected rows that must be found in the request's records


def covers(records: list[dict], rows: list[dict], fields: list[str]) -> bool:
    """Do the request's records hold (nearly) every collected row? A row matches a record on every field the record has."""
    shared = [f for f in fields if any(f in record for record in records[:20])]
    if len(shared) * 2 < len(fields) or not rows:
        return False
    known = {tuple(str(record.get(f, "")).strip() for f in shared) for record in records}
    found = sum(1 for row in rows if tuple(str(row.get(f, "")).strip() for f in shared) in known)
    return found >= MATCH_SHARE * len(rows)


async def find_feed(session: BrowserSession, rows: list[dict], fields: list[str]) -> Feed | None:
    for feed in await session.data_feeds():
        records = records_in(await session.network_body(feed.index, max_chars=10_000_000))
        if records and covers(records, rows, fields):
            return Feed(path=urlparse(feed.url).path, fields=list(fields))
    return None
