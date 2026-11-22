"""Spot the request that carried a page's data: a JSON response holding a list of records.

Like the census, this is evidence the agent is shown, not a rule it must follow: a page that
reveals five items per click usually loaded all of them in one request, with more fields than it prints.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

MIN_RECORDS = 5
FIELD_SAMPLE = 20  # records inspected for the union of field names


@dataclass(frozen=True)
class DataFeed:
    index: int  # the number network_body takes
    method: str
    url: str
    records: int
    fields: list[str]

    def sentence(self) -> str:
        return (f"REQUEST #{self.index} ({self.method} {self.url}) RETURNED {self.records} RECORDS WITH THE FIELDS "
                f"{' | '.join(self.fields)}: network_body({self.index}) READS THEM ALL AT ONCE")


def records_in(body: str) -> list[dict] | None:
    """The list of records in a JSON body: the body itself, or the one list of objects inside an object."""
    try:
        data = json.loads(body)
    except ValueError:
        return None
    if isinstance(data, dict):
        lists = [v for v in data.values() if isinstance(v, list) and v and all(isinstance(r, dict) for r in v)]
        data = lists[0] if len(lists) == 1 else None
    if isinstance(data, list) and len(data) >= MIN_RECORDS and all(isinstance(r, dict) for r in data):
        return data
    return None


def describe(index: int, method: str, url: str, body: str) -> DataFeed | None:
    records = records_in(body)
    if records is None:
        return None
    fields: list[str] = []
    for record in records[:FIELD_SAMPLE]:
        fields += [key for key in record if key not in fields]
    return DataFeed(index, method, url, len(records), fields)
