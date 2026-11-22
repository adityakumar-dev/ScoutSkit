"""Count what the raw page source holds against what the live page shows.

A paged data table keeps every row in the HTML the server sent and then removes all but one page of them
from the live DOM. So "the source has 265 rows, the page shows 25" is evidence that rows are missing from
what the agent can see, and it does not depend on any wording the site chooses to print.

The same pass finds *detail blocks*: label/value tables that repeat once per item (typically in a hidden modal
inside each row) and carry fields the visible table does not show, such as a description or a contact.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from lxml import html as lxml_html

MIN_ROWS = 8  # smaller tables are not worth a warning
DETAIL_LABEL_SHARE = 0.6  # a detail block is a table where most rows are a (label, value) pair
DETAIL_SAMPLE = 20  # blocks read to collect the union of their labels
KEY_PROBES = 10  # collected keys used to recognise which table the agent's rows came from


@dataclass(frozen=True)
class Table:
    selector: str
    rows: int
    text: str = ""  # lowercase text of the whole table, only kept for the raw source (to recognise the agent's rows)


@dataclass(frozen=True)
class Census:
    selector: str
    raw_rows: int
    shown_rows: int

    def sentence(self) -> str:
        return f"the raw page source holds {self.raw_rows} rows in {self.selector}, but the live page shows only {self.shown_rows} of them"


def _selector(table, position: int) -> str:
    if table.get("id"):
        return f"table#{table.get('id')}"
    classes = ".".join((table.get("class") or "").split()[:2])
    return f"table.{classes}" if classes else f"table[{position}]"


def tables(source: str, with_text: bool = False) -> list[Table]:
    """Every table with data rows. Rows are the table's own: tables nested inside its cells are not counted."""
    try:
        root = lxml_html.fromstring(source)
    except (ValueError, lxml_html.etree.ParserError):  # a page we cannot parse simply has no census
        return []
    found = []
    for position, table in enumerate(root.iter("table")):
        rows = [row for row in table.xpath("./tbody/tr | ./tr") if row.xpath("./td")]
        if rows:
            found.append(Table(_selector(table, position), len(rows), table.text_content().lower() if with_text and len(rows) >= MIN_ROWS else ""))
    return found


def compare(raw: list[Table], shown: list[Table], keys: Iterable[str] = ()) -> Census | None:
    """The table that holds more rows in the source than the page shows: the one the agent's rows came from, else the largest."""
    shown_rows = {table.selector: table.rows for table in shown}
    hidden = [table for table in raw if table.rows >= MIN_ROWS and table.rows > shown_rows.get(table.selector, 0)]
    if not hidden:
        return None
    probes = [key.lower() for key in list(keys)[:KEY_PROBES] if key]
    own = [table for table in hidden if any(probe in table.text for probe in probes)]
    best = max(own or hidden, key=lambda table: table.rows)
    return Census(best.selector, best.rows, shown_rows.get(best.selector, 0))


@dataclass(frozen=True)
class DetailBlocks:
    selector: str  # how the repeated blocks are written, e.g. table#settings
    count: int
    labels: tuple[str, ...]  # the fields they hold, in page order
    host: str  # the table whose rows each contain one block, or "" when they sit elsewhere

    def sentence(self) -> str:
        where = f"one inside each row of {self.host}" if self.host else "elsewhere on the page"
        return f"the raw source also holds {self.count} repeated detail blocks ({self.selector}), {where}, with the fields: {' | '.join(self.labels)}"


def _group_key(table) -> str | None:
    if table.get("id"):
        return f"table#{table.get('id')}"
    classes = ".".join((table.get("class") or "").split()[:2])
    return f"table.{classes}" if classes else None


def _labels(table) -> tuple[int, list[str]]:
    """(number of rows, labels of the rows that are a label/value pair) for one table.

    A pair is a header cell followed by a value cell. Real pages put such rows in <thead>, <tbody> or directly in the
    table, so all of them count; a header row of two <th> cells is not a pair."""
    rows = table.xpath("./thead/tr | ./tbody/tr | ./tfoot/tr | ./tr")
    pairs = [cells for row in rows if len(cells := row.xpath("./th | ./td")) == 2 and cells[0].tag == "th" and cells[1].tag == "td"]
    return len(rows), [label for cells in pairs if (label := " ".join(cells[0].text_content().split()))]


def detail_blocks(source: str) -> list[DetailBlocks]:
    """Repeated label/value tables in the source, biggest groups first (at most two)."""
    try:
        root = lxml_html.fromstring(source)
    except (ValueError, lxml_html.etree.ParserError):
        return []
    positions = {table: index for index, table in enumerate(root.iter("table"))}
    groups: dict[str, list] = {}
    for table in positions:
        key = _group_key(table)
        if key:
            groups.setdefault(key, []).append(table)
    found = []
    for key, members in groups.items():
        if len(members) < MIN_ROWS:
            continue
        first_rows, first_labels = _labels(members[0])
        if len(first_labels) < 2 or len(first_labels) < DETAIL_LABEL_SHARE * first_rows:
            continue
        labels: dict[str, None] = {}  # ordered union: a block may omit a field that is empty for its item
        for member in members[:DETAIL_SAMPLE]:
            labels.update(dict.fromkeys(_labels(member)[1]))
        row = next((ancestor for ancestor in members[0].iterancestors("tr")), None)
        host_table = next(row.iterancestors("table"), None) if row is not None else None
        host = _selector(host_table, positions[host_table]) if host_table is not None else ""
        found.append(DetailBlocks(key, len(members), tuple(labels), host))
    return sorted(found, key=lambda block: -block.count)[:2]
