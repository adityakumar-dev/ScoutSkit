"""Sanity checks on extracted rows that grounding cannot make.

Grounding proves every value is on the page. It cannot tell that a "title" cell swallowed a hidden
modal, because the modal's text is on the page too. These checks look for the symptoms.
"""

from __future__ import annotations

from collections import Counter

LONG_VALUE = 60  # a value shorter than this cannot hold other values in a meaningful way
INNER_MIN = 6  # shortest value of another column that counts as "contained"
INNER_COUNT = 2  # a value holding this many other columns' values has swallowed nested content
POLLUTED_SHARE = 0.3  # of the rows
HUGE_VALUE = 5_000  # characters


def quality_warnings(rows: list[dict]) -> list[str]:
    """Plain-language warnings, empty when the rows look clean."""
    warnings: list[str] = []
    polluted: Counter[str] = Counter()
    swallowed: dict[str, Counter[str]] = {}
    for row in rows:
        for column, value in row.items():
            text = str(value)
            if len(text) < LONG_VALUE:
                continue
            inside = [other for other, v in row.items() if other != column and len(str(v).strip()) >= INNER_MIN and str(v).strip() in text]
            if len(inside) >= INNER_COUNT:
                polluted[column] += 1
                swallowed.setdefault(column, Counter()).update(inside)
    for column, count in polluted.most_common(3):
        if count >= POLLUTED_SHARE * len(rows):
            names = ", ".join(f"'{name}'" for name, _ in swallowed[column].most_common(3))
            warnings.append(
                f"column '{column}' looks polluted: in {count} of {len(rows)} rows it also contains the values of other columns ({names}). "
                "The selector probably captured nested content such as a hidden modal or detail block; select only the element that holds this field "
                "(for example the <a> or a specific cell), and put the detail fields in their own columns."
            )
    empty = [column for column in rows[0] if all(not str(row.get(column, "")).strip() for row in rows)] if rows else []
    for column in empty[:3]:
        warnings.append(f"column '{column}' is empty in every row: check that the page really has no value for it, and do not claim it was collected.")
    biggest = max(((len(str(value)), column) for row in rows for column, value in row.items()), default=(0, ""))
    if biggest[0] > HUGE_VALUE and not any(f"'{biggest[1]}'" in warning for warning in warnings):
        warnings.append(f"column '{biggest[1]}' has a value of {biggest[0]:,} characters; check that it is a single field and not a whole container.")
    return warnings
