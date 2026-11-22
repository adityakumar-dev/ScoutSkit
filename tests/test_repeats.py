"""The finder of repeated items: tables and cards alike, a short selector that matches exactly the items, and the agent told about it."""

import pytest

from scoutskit import sandbox
from scoutskit.browser import open_session
from scoutskit.tools import Collector, build_registry

needs_sandbox = pytest.mark.skipif(not sandbox.available(), reason="bubblewrap is not installed")


async def test_cards_whose_colour_class_differs_are_one_list_and_the_selector_matches_exactly_them(portal):
    async with open_session(portal + "/cards.html") as session:
        await session.goto(portal + "/cards.html")
        found = await session.repeats()
    assert found is not None and found.live == 30 and found.raw == 0 and found.tag == "div"  # (the cards are drawn by script: none in the raw source)
    assert found.selector == 'div[data-slot="card"]'  # short, and not the nav links or the options, which repeat too but say little
    assert "Problem statement number 1" in found.text
    paths = [path for path, _ in found.fields]
    assert any(path.startswith("h3") for path in paths) and any('data-slot="badge"' in path for path in paths)


async def test_table_rows_are_found_too_and_a_page_without_a_list_says_so(portal):
    async with open_session(portal + "/records.html") as session:
        await session.goto(portal + "/records.html")
        found = await session.repeats()
        assert found is not None and found.tag == "tr" and found.live >= 8
        assert f"{found.live} TIMES" in found.sentence() and "RENDERED_PATH" in found.sentence()  # drawn by script: not in the raw source
    async with open_session(portal + "/typing.html") as session:
        await session.goto(portal + "/typing.html")
        assert await session.repeats() is None
        registry = build_registry(session, Collector([]))
        with pytest.raises(Exception, match="no list of repeated items"):
            await registry.call("find_items", {})


async def test_find_items_tells_the_agent_what_one_item_holds_and_how_to_extract(portal):
    async with open_session(portal + "/cards.html") as session:
        await session.goto(portal + "/cards.html")
        out, is_read = await build_registry(session, Collector([])).call("find_items", {})
    assert is_read and "div[data-slot=\"card\"]" in out and "30 items on the live page" in out
    assert "PS25000" in out and "use_script_output" in out and "First item's HTML" in out


async def test_a_list_the_page_shows_blocks_a_premature_done(portal):
    async with open_session(portal + "/cards.html") as session:
        await session.goto(portal + "/cards.html")
        registry = build_registry(session, Collector([]), lambda: None)
        with pytest.raises(Exception, match="the page lists 30 items"):
            await registry.call("done", {})


async def test_menus_headers_footers_and_hidden_lists_are_not_the_pages_data(portal):
    """An empty page still shows its navigation: eight menu links must not make it look like a page with a list."""
    from scoutskit.peek import peek
    from scoutskit.browser import open_browser
    from scoutskit.search import Hit

    async with open_session(portal + "/empty_shell.html") as session:
        await session.goto(portal + "/empty_shell.html")
        assert await session.repeats() is None
    async with open_browser() as host:
        looked = await peek(host, Hit("shell", portal + "/empty_shell.html", "", "web"))
    assert looked.items == 0 and looked.empty and looked.rank == 2  # says it has no data: tried last


async def test_a_list_of_sections_that_each_hold_a_longer_list_reports_the_inner_rows(portal):
    """An accordion of programmes, each a table of documents: the rows are the data, not the six sections."""
    async with open_session(portal + "/accordion.html") as session:
        await session.goto(portal + "/accordion.html")
        found = await session.repeats()
    assert found is not None and found.tag == "tr" and found.live == 72  # 6 tables x 12 rows, all matched by the selector
    assert "programme number" in found.text


def test_a_bare_generic_selector_is_not_a_finding():
    from scoutskit.browser.repeats import meaningful

    assert not meaningful({"selector": "div"}) and not meaningful({"selector": " SPAN "})
    assert meaningful({"selector": "tr.bg-white"}) and meaningful({"selector": "tr"}) and meaningful({"selector": 'div[data-slot="card"]'}) and meaningful({"selector": "li"})
