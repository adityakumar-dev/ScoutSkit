import json
import re

import pytest

from scoutskit.agent import Agent
from scoutskit.browser import open_session
from scoutskit.browser.session import ActionError
from scoutskit.browser.feeds import describe
from scoutskit.recorder import RunRecorder
from test_agent_loop import ScriptedChat, plan


def records(n=8):
    return [{"id": i, "title": f"t{i}", "owner": "x"} for i in range(n)]


def test_a_json_list_of_records_is_described_with_all_its_fields():
    feed = describe(3, "GET", "http://s/items.json", json.dumps(records()))
    assert feed and feed.records == 8 and feed.fields == ["id", "title", "owner"]
    assert "network_body(3)" in feed.sentence()


def test_a_list_inside_an_object_counts_but_small_or_plain_json_does_not():
    assert describe(1, "GET", "u", json.dumps({"count": 8, "items": records()})).records == 8
    assert describe(1, "GET", "u", json.dumps(records(3))) is None
    assert describe(1, "GET", "u", json.dumps({"count": 40})) is None
    assert describe(1, "GET", "u", "not json") is None


async def test_the_session_reports_the_request_behind_the_feed_page(portal):
    async with open_session(portal + "/feed.html") as session:
        await session.goto(portal + "/feed.html")
        await session.snapshot()
        (feed,) = await session.data_feeds()
        assert feed.url.endswith("items.json") and feed.records == 40 and feed.fields[-2:] == ["owner", "status"]


async def test_clicking_the_same_button_on_a_page_that_keeps_changing_is_not_a_loop(portal, tmp_path):
    start = portal + "/feed.html"
    clicks = {"n": 0}

    async def brain(page: str) -> dict:
        clicks["n"] += 1
        if clicks["n"] <= 7:
            ref = re.search(r'button "Load more".*?\[ref=(e\d+)\]', page).group(1)
            return {"tool": "click", "args": {"ref": ref}}
        return {"tool": "fail", "args": {"reason": "stop here"}}

    async with open_session(start) as session:
        result = await Agent(session, [ScriptedChat(brain=brain)], ["scripted"], RunRecorder(tmp_path), max_steps=10).run(
            "get every item", plan(start_url=start, item_name="item", min_items=40))
    assert result.message == "stop here"  # not "stuck repeating the same step"


async def test_values_that_came_from_the_request_are_accepted_as_grounded(portal, tmp_path):
    from scoutskit.tools import Collector, build_registry

    start = portal + "/feed.html"
    async with open_session(start) as session:
        await session.goto(start)
        await session.snapshot()  # only five items are on screen; owner and status are not on the page at all
        registry = build_registry(session, Collector([], ""), workdir=tmp_path / "code")
        body = json.loads(await session.network_body(next(f.index for f in await session.data_feeds())))
        text, _ = await registry.call("extract_rows", {"rows": body})
        assert "+40 new" in text and "0 rejected" in text
        invented = [{**body[0], "id": "F999", "title": "A title nobody ever served", "owner": "nobody-ever-heard-of"}]
        with pytest.raises(ActionError, match="not on the current page"):
            await registry.call("extract_rows", {"rows": invented})


def test_a_column_that_is_empty_in_every_row_is_flagged():
    from scoutskit.quality import quality_warnings

    rows = [{"id": i, "title": f"title {i}", "owner": ""} for i in range(10)]
    (warning,) = quality_warnings(rows)
    assert "column 'owner' is empty in every row" in warning
