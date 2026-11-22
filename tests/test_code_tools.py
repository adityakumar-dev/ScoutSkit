"""The code-writing path: the agent reads slices of the raw HTML, writes a script, and loads its output.

The catalog page keeps all 60 rows in its raw HTML but only 10 in the live DOM (like a paged data
table), so the only way to get all 60 is to read the source, as on the real SIH page.
"""

import json

import pytest

from scoutskit import sandbox
from scoutskit.agent import Agent
from scoutskit.browser import open_session
from scoutskit.recorder import RunRecorder
from scoutskit.tools import Collector, build_registry
from test_agent_loop import ScriptedChat, plan, ref

pytestmark = pytest.mark.skipif(not sandbox.available(), reason="bubblewrap is not installed")

SCRIPT = """from bs4 import BeautifulSoup
import json
soup = BeautifulSoup(open(HTML_PATH, encoding='utf-8').read(), 'lxml')
rows = [{'code': tds[0].text, 'name': tds[1].text, 'group': tds[2].text}
        for tr in soup.select('#items tbody tr') if len(tds := tr.find_all('td')) == 3]
json.dump(rows, open(OUT_PATH, 'w'))
print(len(rows), 'rows;', len({r['code'] for r in rows}), 'unique;', rows[0])
"""


class Navigator:
    """Opens the menu and the catalog, then hands control to the given continuation."""

    def __init__(self, then) -> None:
        self.then, self.turn = then, 0

    async def __call__(self, page: str) -> dict:
        tree = page.split("TREE:\n", 1)[1]
        if "catalog.html" not in page.split("CURRENT PAGE:", 1)[1].split("\n", 1)[0]:
            if link := ref(tree, r'link "Catalog"'):
                return {"tool": "click", "args": {"ref": link}}
            return {"tool": "click", "args": {"ref": ref(tree, r'button "Toggle navigation"')}}
        self.turn += 1
        return await self.then(self.turn, page)


async def run(portal, tmp_path, then, **plan_overrides):
    start = portal + "/index.html"
    async with open_session(start) as session:
        recorder = RunRecorder(tmp_path)
        agent = Agent(session, [ScriptedChat(brain=Navigator(then))], ["scripted"], recorder, max_steps=20)
        result = await agent.run("get the catalog", plan(**{"start_url": start, "item_name": "item", "min_items": 60, **plan_overrides}))
    return result, recorder


async def test_code_extracts_rows_that_the_live_page_does_not_show(portal, tmp_path):
    async def script(turn, page):
        steps = [
            {"tool": "grep_source", "args": {"pattern": "<tr>"}},
            {"tool": "view_source", "args": {"start": 10, "end": 14}},
            {"tool": "run_python", "args": {"code": SCRIPT}},
            {"tool": "use_script_output", "args": {}},
            {"tool": "done", "args": {}},
        ]
        return steps[min(turn - 1, len(steps) - 1)]

    result, recorder = await run(portal, tmp_path, script)
    assert result.status == "completed", result.message
    assert sorted(r["code"] for r in result.rows) == [f"C{i:03d}" for i in range(1, 61)]
    assert result.fields == ["code", "name", "group"]
    log = [json.loads(line) for line in (recorder.dir / "actions.jsonl").read_text().splitlines()]
    assert not [e["error"] for e in log if e.get("ok") is False]
    assert (recorder.dir / "code" / "script_01.py").exists()


async def test_rows_typed_from_memory_are_rejected_as_not_on_the_page(portal, tmp_path):
    invented = [{"code": f"C{i:03d}", "name": f"Catalog item {i}", "group": "Alpha"} for i in range(11, 21)]  # rows 11-20 are NOT in the live page

    async def liar(turn, page):
        return {"tool": "extract_rows", "args": {"rows": invented}} if turn == 1 else {"tool": "fail", "args": {"reason": "stop"}}

    result, recorder = await run(portal, tmp_path, liar)
    assert not result.rows
    log = [json.loads(line) for line in (recorder.dir / "actions.jsonl").read_text().splitlines()]
    assert "not on the current page" in next(e["error"] for e in log if e.get("tool") == "extract_rows")


async def test_script_rows_that_are_not_on_the_page_are_rejected(portal, tmp_path):
    cheat = ("import json\njson.dump([{'code': f'C{i:03d}', 'name': f'Catalog item {i}', 'group': 'Alpha'} for i in range(500, 520)], open(OUT_PATH, 'w'))\nprint('wrote')")

    async def cheater(turn, page):
        steps = [{"tool": "run_python", "args": {"code": cheat}}, {"tool": "use_script_output", "args": {}}, {"tool": "fail", "args": {"reason": "stop"}}]
        return steps[min(turn - 1, 2)]

    result, recorder = await run(portal, tmp_path, cheater)
    assert not result.rows
    log = [json.loads(line) for line in (recorder.dir / "actions.jsonl").read_text().splitlines()]
    assert "rejected as not on the page" in next(e["error"] for e in log if e.get("tool") == "use_script_output")


async def test_a_crashing_script_comes_back_with_a_hint_to_fix_it(portal, tmp_path):
    async with open_session(portal + "/catalog.html") as session:
        await session.goto(portal + "/catalog.html")
        registry = build_registry(session, Collector([], ""), workdir=tmp_path / "code")
        text, _ = await registry.call("run_python", {"code": "rows = []\nprint(rows[0])"})
        assert "IndexError" in text and "fix the bug shown above" in text


async def test_a_script_that_read_the_live_page_is_warned_that_rows_are_missing(portal, tmp_path):
    live_only = SCRIPT.replace("HTML_PATH", "RENDERED_PATH")  # the live page holds only the 10 rows it shows
    async with open_session(portal + "/catalog.html") as session:
        await session.goto(portal + "/catalog.html")
        registry = build_registry(session, Collector([], ""), workdir=tmp_path / "code")
        await registry.call("run_python", {"code": live_only})
        text, _ = await registry.call("use_script_output", {})
        assert "10 kept" in text and "WARNING: the page states 60 entries but only 10 were loaded" in text
        assert "read HTML_PATH" in text
        full, _ = await registry.call("run_python", {"code": SCRIPT})  # the raw source holds all 60
        text, _ = await registry.call("use_script_output", {})
        assert "60 kept" in text and "WARNING" not in text
