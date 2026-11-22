"""Reject extracted rows whose values are not on the page.

A model asked to copy data can invent plausible rows (a real run produced 25 of them and
reported success). Every value of a row must be found in the page's own text; rows that
are not grounded are rejected with a reason the model can act on.
"""

from __future__ import annotations

from .values import plain
import html
import re

TAGS = re.compile(r"<[^>]+>")
SPACE = re.compile(r"\s+")
MIN_LEN = 3  # shorter values ("1", "a") cannot be judged
FUZZY_MIN_LEN = 24  # longer values tolerate a small typo: 2 of 3 probes (start, middle, end) must be found
MAX_MISSING_SHARE = 0.2


def norm(value: object) -> str:
    return SPACE.sub(" ", str(value)).strip().lower()


def corpus(*texts: str) -> str:
    """Lowercased page text with tags removed, entities decoded and whitespace collapsed."""
    return "\n".join(norm(html.unescape(TAGS.sub(" ", text) if "<" in text else text)) for text in texts)


def value_grounded(value: object, text: str) -> bool:
    v = norm(value)
    if len(v) < MIN_LEN or v in text:
        return True
    if len(v) < FUZZY_MIN_LEN:
        return False
    middle = len(v) // 2
    probes = (v[:20], v[middle - 10 : middle + 10], v[-20:])
    return sum(probe in text for probe in probes) >= 2


def _parts(value: object) -> list:
    """The pieces of a field that must each be on the page: the elements of a list, else the value itself."""
    if isinstance(value, (list, tuple)):
        return [part for item in value for part in _parts(item)]
    if isinstance(value, dict):
        return [part for item in value.values() for part in _parts(item)]
    return [value]


def ground_rows(rows: list[dict], text: str, key_field: str = "") -> tuple[list[dict], list[tuple[dict, str]]]:
    """Split rows into (grounded, [(rejected row, reason)]). `text` comes from corpus()."""
    good: list[dict] = []
    bad: list[tuple[dict, str]] = []
    for row in rows:
        parts = {k: _parts(v) for k, v in row.items()}  # a list is several cells on a page, never one "a; b" cell
        row = {k: plain(v) if isinstance(v, (list, tuple, dict)) else v for k, v in row.items()}
        values = [(k, v) for k, v in row.items() if v is not None and len(norm(v)) >= MIN_LEN]
        if not values:
            bad.append((row, "the row is empty"))
            continue
        missing = [k for k, v in values if not all(value_grounded(part, text) for part in parts[k] if len(norm(part)) >= MIN_LEN)]
        if (key_field and key_field in missing) or len(missing) > MAX_MISSING_SHARE * len(values):
            bad.append((row, "not found on the page: " + ", ".join(f"{k}={str(row[k])[:40]!r}" for k in missing[:3])))
        else:
            good.append(row)
    return good, bad
