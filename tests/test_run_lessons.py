"""Lessons from a real multi-site run: list-valued fields, a key that repeats, a path given to BeautifulSoup, printing instead of saving, refused hosts."""

import pytest

from scoutskit import team as team_module
from scoutskit.brief import _key_of
from scoutskit.browser import open_session
from scoutskit.provider.llm import LLMResult
from scoutskit.tools import Collector, build_registry
from scoutskit.values import plain
from scoutskit import sandbox

needs_sandbox = pytest.mark.skipif(not sandbox.available(), reason="bubblewrap is not installed")


def test_lists_and_objects_become_text_a_cell_can_hold():
    assert plain(["Intel Core i3", "8 GB", None, ""]) == "Intel Core i3; 8 GB"
    assert plain({"ram": "8 GB", "ssd": ""}) == "ram: 8 GB" and plain(None) == "" and plain(3.0) == "3" and plain(" x ") == "x"
    collector = Collector(["name", "specs"], "name")
    assert collector.add([{"name": "Laptop A", "specs": ["i3", "8 GB"]}]) == (1, 0, 0)
    assert collector.rows["laptop a"]["specs"] == "i3; 8 GB"


async def test_a_row_with_a_list_field_is_checked_against_the_page_as_text(portal):
    async with open_session(portal + "/index.html") as session:
        await session.goto(portal + "/index.html")
        text = (await session.visible_text()).split()
        words = [w for w in text if len(w) > 3][:3]
        registry = build_registry(session, Collector([]))
        out, _ = await registry.call("extract_rows", {"rows": [{"name": words[0], "parts": words[1:3]}]})
        assert "+1 new" in out  # each part is on the page; "['a', 'b']" or "a; b" as one string would be found nowhere
        with pytest.raises(Exception, match="not found on the page"):
            await registry.call("extract_rows", {"rows": [{"name": words[0] + "x", "parts": ["invented one", "invented two"]}]})


def test_the_key_is_never_just_the_first_column_when_a_better_one_exists():
    assert _key_of(["price", "model_name", "specifications"], None) == "model_name"
    assert _key_of(["price", "rating"], None) == "price"  # nothing better: the first
    assert _key_of(["price", "model_name"], "price") == "price"  # what the model named wins
    assert _key_of([], None) == ""


@needs_sandbox
async def test_the_agent_is_told_when_it_only_printed(portal, tmp_path):
    async with open_session(portal + "/index.html") as session:
        await session.goto(portal + "/index.html")
        registry = build_registry(session, Collector([]), workdir=tmp_path / "code")
        out, _ = await registry.call("run_python", {"code": "print(len(HTML))"})
        assert "nothing was saved: printing is not collecting" in out
        out, _ = await registry.call("run_python", {"code": "import json\njson.dump([{'a': 'x'}], open(OUT_PATH, 'w'))"})
        assert "nothing was saved" not in out  # it wrote its records


def test_a_host_that_refused_us_is_not_tried_again_through_another_page():
    assert team_module.REFUSED.search("https://www.smartprix.com/x answered HTTP 403")
    assert team_module.REFUSED.search("a website refused the browser: x showed a block page (/captcha)")
    assert not team_module.REFUSED.search("net::ERR_HTTP2_PROTOCOL_ERROR")  # a broken connection says nothing about other pages


@needs_sandbox
async def test_the_path_mistake_just_works_and_the_page_text_is_at_hand(portal, tmp_path):
    async with open_session(portal + "/index.html") as session:
        await session.goto(portal + "/index.html")
        registry = build_registry(session, Collector([]), workdir=tmp_path / "code")
        code = "from bs4 import BeautifulSoup\nprint(len(BeautifulSoup(HTML_PATH, 'lxml').get_text()) > 20, len(HTML) > 100, len(RENDERED) > 100)"
        out, _ = await registry.call("run_python", {"code": code})
        assert out.splitlines()[0] == "True True True" and "Warning" not in out  # the path was read as the document it names


def test_the_same_failure_is_recognised_whatever_the_numbers_and_wording_around_it():
    from scoutskit.agent import _failure_of

    a = _failure_of([], "Error: table#dataTablePS not found in the raw source. Cannot proceed.\nTraceback (most recent call last):\n  File \"/work/script_05.py\", line 79\nTypeError: x")
    b = _failure_of([], "Error: table#dataTablePS not found in the raw source. Cannot proceed.\nTraceback (most recent call last):\n  File \"/work/script_12.py\", line 83\nTypeError: x")
    assert a == b and a  # script numbers and line numbers do not make it a new error
    assert _failure_of([], "Total rows: 21") == "" and _failure_of(["click failed: no such element"], "") .startswith("click failed")


def test_older_turns_are_cut_short_but_the_newest_stay_whole():
    from langchain_core.messages import AIMessage, ToolMessage

    from scoutskit.agent import FRESH_TURNS, OLD_CODE_CHARS, OLD_OUTPUT_CHARS, _thinned

    big, code = "x" * 5000, "print(1)\n" * 200
    history = []
    for n in range(5):
        history.append(AIMessage("", tool_calls=[{"name": "run_python", "args": {"code": code}, "id": f"c{n}"}]))
        history.append(ToolMessage(big, tool_call_id=f"c{n}"))
    thinned = _thinned(history)
    assert len(thinned) == len(history) and history[1].content == big  # the original history is not changed
    old_tool, new_tool = thinned[1], thinned[-1]
    assert len(old_tool.content) < OLD_OUTPUT_CHARS + 100 and "left out" in old_tool.content
    assert new_tool.content == big and thinned[-2].tool_calls[0]["args"]["code"] == code  # the newest turns whole
    assert len(thinned[0].tool_calls[0]["args"]["code"]) < OLD_CODE_CHARS + 80 and thinned[0].tool_calls[0]["id"] == "c0"  # still a valid call
    fresh_starts = len(history) - 2 * FRESH_TURNS
    assert all(thinned[i].content == big for i in range(fresh_starts + 1, len(history), 2))
    assert _thinned(history[:2 * FRESH_TURNS]) == history[:2 * FRESH_TURNS]  # a short history is left alone


def test_a_page_that_says_it_has_no_data_is_recognised():
    from scoutskit.agent import NO_DATA

    for text in ('cell "No data available in table"', "No results found", "0 results", "No matching records found"):
        assert NO_DATA.search(text), text
    for text in ("Showing 10 results", "10 results", "Data available soon"):
        assert not NO_DATA.search(text), text
