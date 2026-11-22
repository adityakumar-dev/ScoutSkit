"""The rows gathered so far, keyed by the item's identifying field."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from ..values import plain

KEY_NAME = re.compile(r"(^|[_\s])(id|number|no|code)$")


@dataclass
class Collector:
    fields: list[str]  # empty until the first rows arrive when the user named no fields
    key_field: str = ""
    rows: dict[str, dict[str, str]] = field(default_factory=dict)

    def ensure_fields(self, sample: dict) -> None:
        if not self.fields:
            self._adopt(sample)

    def _adopt(self, sample: dict) -> None:
        """No fields were named: use the page's own column names from the first row."""
        self.fields = [str(k) for k in sample]
        if self.fields and not self.key_field:
            filled = [f for f in self.fields if str(sample.get(f) or "").strip()]  # a "Sl. No." column the page leaves blank identifies nothing
            self.key_field = next((f for f in filled if KEY_NAME.search(f.lower())), filled[0] if filled else self.fields[0])

    def add(self, raw_rows: object) -> tuple[int, int, int]:
        """Add valid rows; returns (added, duplicates, rejected)."""
        added = duplicates = rejected = 0
        for raw in raw_rows if isinstance(raw_rows, list) else []:
            if not isinstance(raw, dict):
                rejected += 1
                continue
            if not self.fields:
                self._adopt(raw)
            row = {f: plain(raw.get(f)) for f in self.fields}
            # Without its key value a row is still an item if it holds anything: then the whole row identifies it.
            key = (row[self.key_field] or " | ".join(v for v in row.values() if v)).lower()
            if not key:
                rejected += 1
            elif key in self.rows:
                duplicates += 1
            else:
                self.rows[key] = row
                added += 1
        return added, duplicates, rejected
