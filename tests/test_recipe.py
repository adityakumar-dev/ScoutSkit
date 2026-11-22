"""A completed run becomes a recipe; the recipe replays with no model and reports what no longer matches."""

import json
import re

import pytest

from scoutskit import sandbox
from scoutskit.agent import Agent
from scoutskit.browser import open_session
from scoutskit.recipe import Recipe, from_run, replay
from scoutskit.recorder import RunRecorder
from test_agent_loop import ScriptedChat, plan

pytestmark = pytest.mark.skipif(not sandbox.available(), reason="bubblewrap is not installed")

READS_PAGE = """from bs4 import BeautifulSoup
import json
soup = BeautifulSoup(open(RENDERED_PATH, encoding='utf-8').read(), 'lxml')
rows = [{'id': li.text.split(' - ')[0], 'title': li.text.split(' - ')[1]} for li in soup.select('#list li')]
json.dump(rows, open(OUT_PATH, 'w'))
"""
TYPED_IN = """import json
json.dump([{'id': f'F{i:03d}', 'title': f'Feed item {i}'} for i in range(1, 16)], open(OUT_PATH, 'w'))
"""


async def record(portal, tmp_path, script):
    """Run the agent (scripted) on the feed page: two 'Load more' clicks, then the script."""
    start = portal + "/feed.html"
    calls = {"n": 0}

    async def brain(page: str) -> dict:
        calls["n"] += 1
        load_more = {"tool": "click", "args": {"ref": re.search(r'button "Load more".*?\[ref=(e\d+)\]', page).group(1)}}
        sequence = [load_more, load_more, {"tool": "run_python", "args": {"code": script}},
                    {"tool": "use_script_output", "args": {}}, {"tool": "done", "args": {}}]
        return sequence[min(calls["n"] - 1, len(sequence) - 1)]

    async with open_session(start) as session:
        recorder = RunRecorder(tmp_path)
        result = await Agent(session, [ScriptedChat(brain=brain)], ["scripted"], recorder, max_steps=10).run(
            "get the feed", plan(start_url=start, item_name="item", min_items=10))
        assert result.status == "completed" and len(result.rows) == 15
    recorder.save_result(result.rows, result.fields, {"items": len(result.rows)})
    return recorder.dir


async def test_a_run_becomes_a_recipe_of_named_targets_and_a_page_reading_script(portal, tmp_path):
    recipe = from_run(await record(portal, tmp_path, READS_PAGE))
    assert [s.tool for s in recipe.steps] == ["click", "click", "run_python", "use_script_output"]
    assert recipe.steps[0].target == 'button "Load more"' and "ref" not in recipe.steps[0].args
    assert recipe.steps[0].url_path == "/feed.html" and recipe.expected_items == 15 and recipe.extracts
    recipe.save(tmp_path / "recipe.json")
    assert Recipe.load(tmp_path / "recipe.json") == recipe


async def test_the_recipe_replays_without_a_model_and_gets_the_same_data(portal, tmp_path):
    recipe = from_run(await record(portal, tmp_path, READS_PAGE))
    async with open_session(recipe.start_url) as session:
        report = await replay(session, recipe, tmp_path / "replay")
    assert report.status == "replayed" and report.steps_done == 4 and not report.findings
    assert len(report.rows) == 15 and report.fields == ["id", "title"]


async def test_a_script_that_only_holds_typed_in_data_is_not_replayed_as_if_it_read_the_page(portal, tmp_path):
    recipe = from_run(await record(portal, tmp_path, TYPED_IN))
    assert not recipe.extracts and [s.tool for s in recipe.steps] == ["click", "click"]
    async with open_session(recipe.start_url) as session:
        report = await replay(session, recipe, tmp_path / "replay")
    assert report.status == "changed" and [f.kind for f in report.findings] == ["no_extraction"] and report.rows == []


async def test_a_page_without_the_recorded_button_is_reported_not_guessed_at(portal, tmp_path):
    recipe = from_run(await record(portal, tmp_path, READS_PAGE))
    async with open_session(portal + "/details.html") as session:
        report = await replay(session, recipe, tmp_path / "replay", start_url=portal + "/details.html")
    kinds = [f.kind for f in report.findings]
    assert report.status == "diverged" and kinds == ["page_changed", "target_missing"]
    assert 'no element button "Load more"' in report.findings[1].detail and report.steps_done == 0


async def test_a_different_result_size_is_flagged(portal, tmp_path):
    recipe = from_run(await record(portal, tmp_path, READS_PAGE))
    recipe.steps.pop(1)  # one click fewer: the page then shows 10 items, not 15
    async with open_session(recipe.start_url) as session:
        report = await replay(session, recipe, tmp_path / "replay")
    assert report.status == "changed" and report.findings[0].kind == "result_changed"
    assert "collected 15 items, this replay 10" in report.findings[0].detail


async def find_the_request(portal):
    """Open the feed page and look for the request behind its rows."""
    from scoutskit.recipe import find_feed

    start = portal + "/feed.html"
    async with open_session(start) as session:
        await session.goto(start)
        await session.snapshot()
        (feed,) = await session.data_feeds()
        rows = json.loads(await session.network_body(feed.index))
        found = await find_feed(session, rows, list(rows[0]))
        shown_only = await find_feed(session, rows[:5], ["id", "title"])
    return found, shown_only, rows


async def test_the_request_behind_the_rows_is_found_and_unrelated_rows_do_not_match(portal, tmp_path):
    found, shown_only, rows = await find_the_request(portal)
    assert found.path == "/items.json" and found.fields == ["id", "title", "category", "owner", "status"]
    assert shown_only is not None  # a subset of the visible columns still comes from that request
    from scoutskit.recipe.source import covers

    assert not covers(rows, [{"id": "X1", "title": "never served"}] * 3, ["id", "title"])
    assert not covers(rows, rows, ["nothing", "matches"])


async def test_a_recipe_built_on_a_data_request_replays_by_reading_that_request_again(portal, tmp_path):
    from scoutskit.recipe import Feed

    found, _, rows = await find_the_request(portal)
    run = tmp_path / "run"
    run.mkdir()
    (run / "actions.jsonl").write_text(json.dumps({"event": "start", "task": "feed", "plan": {"start_url": portal + "/feed.html"}}) + "\n")
    (run / "result.json").write_text(json.dumps({"summary": {"items": 40}, "rows": rows}))
    recipe = from_run(run, found)
    assert recipe.feed == found and recipe.extracts and recipe.steps == []
    recipe.save(tmp_path / "recipe.json")
    assert Recipe.load(tmp_path / "recipe.json").feed == Feed("/items.json", found.fields)
    async with open_session(recipe.start_url) as session:
        report = await replay(session, recipe, tmp_path / "replay")
    assert report.status == "replayed" and len(report.rows) == 40
    assert report.rows[7] == {k: str(v) for k, v in rows[7].items()}  # owner and status too: they are not on the page
    async with open_session(portal + "/details.html") as session:
        report = await replay(session, recipe, tmp_path / "replay2", start_url=portal + "/details.html")
    assert report.status == "diverged" and report.findings[0].kind == "feed_missing" and report.rows == []
