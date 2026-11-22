"""The agent learns that each item carries more fields than the visible table shows, and can collect them."""

import json

import pytest

from scoutskit import sandbox
from scoutskit.agent import Agent
from scoutskit.browser import open_session
from scoutskit.recorder import RunRecorder
from test_agent_loop import ScriptedChat, plan

pytestmark = pytest.mark.skipif(not sandbox.available(), reason="bubblewrap is not installed")

SCRIPT = """from bs4 import BeautifulSoup
import json
soup = BeautifulSoup(open(HTML_PATH, encoding='utf-8').read(), 'lxml')
rows = []
for tr in soup.select('#items tbody tr'):
    record = {}
    for line in tr.select('table.detail tr'):
        cells = line.find_all(['th', 'td'])
        record[cells[0].text.strip()] = cells[1].text.strip()
    rows.append(record)
json.dump(rows, open(OUT_PATH, 'w'))
print(len(rows), rows[0])
"""


async def test_the_hidden_fields_are_announced_and_collected(portal, tmp_path):
    prompts, steps = [], [
        {"tool": "run_python", "args": {"code": SCRIPT}},
        {"tool": "use_script_output", "args": {}},
        {"tool": "done", "args": {}},
    ]

    async def brain(page: str) -> dict:
        prompts.append(page)
        return steps[min(len(prompts) - 1, len(steps) - 1)]

    start = portal + "/details.html"
    async with open_session(start) as session:
        recorder = RunRecorder(tmp_path)
        result = await Agent(session, [ScriptedChat(brain=brain)], ["scripted"], recorder, max_steps=10).run(
            "get every item with all its fields", plan(start_url=start, item_name="item", min_items=20))

    announced = prompts[0].split("MORE FIELDS PER ITEM IN THE SOURCE: ", 1)[1].split("\n", 1)[0]
    assert "20 repeated detail blocks (table.detail), one inside each row of table#items" in announced
    assert "Code | Name | Owner | Note" in announced  # the visible table has only Code and Name
    assert result.status == "completed" and len(result.rows) == 20
    assert result.fields == ["Code", "Name", "Owner", "Note"]
    assert result.rows[4]["Note"] == "Note text for item 5"
    log = [json.loads(line) for line in (recorder.dir / "actions.jsonl").read_text().splitlines()]
    assert all(e["ok"] for e in log if e.get("tool"))  # every extracted value was found on the page

