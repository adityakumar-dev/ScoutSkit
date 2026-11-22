"""Tools that turn page content into the result: typed rows, or rows produced by a sandboxed script.

Every row is checked against the page text first (see grounding.py), so nothing invented gets in.
"""

from __future__ import annotations

import json
import time

from .. import sandbox
from ..browser import ActionError
from ..grounding import corpus, ground_rows
from ..quality import quality_warnings
from .context import ToolContext
from .registry import Tool, ToolRegistry

EXTRACT_HELP = "Record the items visible on the current page, one object per item with the fields {fields}."
EXTRACT_HELP_OPEN = (
    "Record the items visible on the current page, one object per item, using the page's own column names in snake_case "
    "(the column that identifies the item first). Use the same names every time."
)


def register(registry: ToolRegistry, ctx: ToolContext) -> None:
    session, collector, workdir = ctx.session, ctx.collector, ctx.workdir

    async def extract_rows(rows: list) -> str:
        dicts = [r for r in rows if isinstance(r, dict)]
        if dicts:
            collector.ensure_fields(dicts[0])
        good, bad = ground_rows(dicts, corpus(await session.visible_text(), await session.network_text()), collector.key_field)
        added, dupes, rejected = collector.add(good)
        rejected += (len(rows) - len(dicts)) + len(bad)
        text = f"extracted: +{added} new, {dupes} duplicate, {rejected} rejected; total {len(collector.rows)}"
        if bad:
            text += f". Rejected because they are not on the current page ({bad[0][1]}). Copy only what is on the page, or open the page that shows them."
        if added == 0 and rejected:
            raise ActionError(text if bad else f"{rejected} rows had no {collector.key_field}: this page may not list real items of the requested kind")
        return text

    async def find_items() -> str:
        found = await session.repeats()
        if found is None:
            raise ActionError("this page has no list of repeated items (fewer than 5 alike): use read_page, grep_source or inspect_element to see what it holds")
        return found.describe()

    async def run_python(code: str) -> str:
        if workdir is None:
            raise ActionError("code execution is not available in this run")
        raw, _ = await session.source_html("raw")
        rendered, _ = await session.source_html("rendered")
        workdir.mkdir(parents=True, exist_ok=True)
        raw_path, rendered_path = workdir / "source_raw.html", workdir / "source_rendered.html"
        raw_path.write_text(raw, encoding="utf-8")
        rendered_path.write_text(rendered, encoding="utf-8")
        started = time.time()
        output = await sandbox.run_python(str(code), work=workdir, raw_html=raw_path, rendered_html=rendered_path)
        if "Traceback (most recent call last)" in output:
            output += "\n[the script crashed: fix the bug shown above and run it again; do not give up on code]"
        out_file = workdir / "out.json"
        if not out_file.exists() or out_file.stat().st_mtime < started:
            output += "\n[nothing was saved: printing is not collecting. To keep records, json.dump(list_of_dicts, open(OUT_PATH, 'w')) then call use_script_output]"
        return output

    async def use_script_output() -> str:
        out = workdir / "out.json" if workdir else None
        if out is None or not out.exists():
            raise ActionError("no output yet: the script must write a JSON list of objects to OUT_PATH")
        try:
            rows = json.loads(out.read_text(encoding="utf-8"))
        except ValueError as error:
            raise ActionError(f"OUT_PATH is not valid JSON ({error})") from error
        if not isinstance(rows, list) or not rows or not all(isinstance(r, dict) for r in rows):
            raise ActionError("OUT_PATH must hold a non-empty JSON list of objects (one per record)")
        raw, _ = await session.source_html("raw")
        rendered, _ = await session.source_html("rendered")
        collector.rows.clear()  # the script's output is the full dataset
        collector.ensure_fields(rows[0])
        good, bad = ground_rows(rows, corpus(raw, rendered, await session.network_text()), collector.key_field)
        added, dupes, _ = collector.add(good)
        text = f"loaded {len(rows)} rows from the script: {added} kept, {dupes} duplicate, {len(bad)} rejected as not on the page; total {len(collector.rows)}"
        if bad:
            text += f". Example rejection: {bad[0][1]}"
        if not added:
            raise ActionError(text)
        stated, census = await session.stated_total(), await session.census(list(collector.rows))
        if stated and added < stated:
            text += f". WARNING: the page states {stated} entries but only {added} were loaded"
        elif census and added < census.raw_rows:
            text += f". WARNING: {census.sentence()}, but only {added} were loaded"
        if (stated and added < stated) or (census and added < census.raw_rows):
            text += ". A script that reads RENDERED_PATH only sees the rows currently shown; read HTML_PATH (the raw source) instead."
        for warning in quality_warnings(good):
            text += f". WARNING: {warning}"
        return text

    for tool in (
        Tool("extract_rows", EXTRACT_HELP.format(fields=collector.fields) if collector.fields else EXTRACT_HELP_OPEN,
             {"rows": "list of objects"}, extract_rows),
        Tool("find_items", "Find the list of repeated items on this page (table rows, cards, entries): the CSS selector that matches them, how many there are "
             "(live page and raw source), what one item contains and its HTML. Use it FIRST for any list, then write one script with that selector.",
             {}, find_items, reads=True),
        Tool("run_python", "Run Python 3 (standard library + beautifulsoup4 + lxml, no network) to extract data from the page. HTML_PATH is the RAW document "
             "as the server sent it (use it first: it often holds rows the page hides); RENDERED_PATH is the live DOM (only what is shown now); "
             "OUT_PATH is where to save results. All three are already-defined PATHS (file names): HTML and RENDERED are the same two documents as text, "
             "and BeautifulSoup(HTML_PATH, 'lxml') also works. Save a JSON list of objects, one per record, using the page's own "
             "field names: json.dump(rows, open(OUT_PATH, 'w'), ensure_ascii=False). Print only short summaries (counts, empty fields, 2 sample rows).",
             {"code": "the Python script"}, run_python, reads=True),
        Tool("use_script_output", "Load the rows the script saved to OUT_PATH into the result (replaces everything collected so far). "
             "Rows whose values are not on the page are rejected.", {}, use_script_output),
    ):
        registry.register(tool)
