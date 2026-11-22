"""Read the total a page states about its own list ("Showing 1 to 25 of 265 entries").

That sentence is evidence of how many items exist. It lets the agent check that it collected
everything, and a stated reason cannot override it.
"""

from __future__ import annotations

import re

NOUN = r"(?:entries|results|records|items|rows)"
PATTERNS = (
    re.compile(rf"\bshowing\s+[\d,]+\s+to\s+[\d,]+\s+of\s+([\d,]+)\s+{NOUN}\b", re.IGNORECASE),  # DataTables and most tables
    re.compile(rf"\b(?:of|out of)\s+([\d,]+)\s+{NOUN}\b", re.IGNORECASE),
    re.compile(rf"\b([\d,]+)\s+{NOUN}\s+found\b", re.IGNORECASE),
    re.compile(rf"\btotal(?:\s+{NOUN})?\s*[:=]\s*([\d,]+)", re.IGNORECASE),
)


def stated_total(text: str) -> int | None:
    """The first total the text states, or None. The first match wins, so a filtered list reports its filtered size."""
    for pattern in PATTERNS:
        match = pattern.search(text)
        if match:
            return int(match.group(1).replace(",", ""))
    return None
