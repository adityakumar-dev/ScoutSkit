"""Turning what a model wrote into a field's text. A list or object is not a cell: "['Intel Core i3', '8 GB']" is nowhere on a page."""

from __future__ import annotations

import json


def plain(value: object) -> str:
    """Text for one field: lists become "a; b", objects "key: value; ...", missing values are empty."""
    if value is None:
        return ""
    if isinstance(value, (list, tuple)):
        return "; ".join(part for part in (plain(v) for v in value) if part)
    if isinstance(value, dict):
        return "; ".join(f"{k}: {plain(v)}" for k, v in value.items() if plain(v))
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value).strip() if not isinstance(value, str) else value.strip()
