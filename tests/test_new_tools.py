"""hover, wait_for, tabs, find and javascript_tool, each against a page built to need it."""

import pytest

from scoutskit.browser import ActionError, open_session
from scoutskit.browser.tree import find
from test_session import ref_of


async def test_hover_reveals_a_menu_that_a_click_would_not(portal):
    async with open_session(portal + "/hover.html") as s:
        await s.goto(portal + "/hover.html")
        tree, _ = await s.snapshot()
        assert "Hidden records link" not in tree
        await s.hover(ref_of(tree, r'button "Services"'))
        tree, _ = await s.snapshot()
        assert 'link "Hidden records link"' in tree


async def test_wait_for_text_that_appears_later_and_text_that_never_does(portal):
    async with open_session(portal + "/delayed.html") as s:
        await s.goto(portal + "/delayed.html")
        assert "is on the page" in await s.wait_for("Ready now", timeout=5)
        assert "did not appear" in await s.wait_for("never shown", timeout=1)
        assert await s.wait_for(seconds=0.2) == "waited 0.2s"


async def test_a_link_that_opens_a_new_tab_is_followed_and_tabs_can_be_managed(portal):
    async with open_session(portal + "/tabs.html") as s:
        await s.goto(portal + "/tabs.html")
        tree, _ = await s.snapshot()
        await s.click(ref_of(tree, r'link "Open records in a new tab"'))
        assert s.page.url.endswith("/records.html")  # the new same-site tab became the active one
        listing = await s.list_tabs()
        assert listing.count("\n") == 1 and "[active]" in listing.splitlines()[1]
        assert (await s.switch_tab(0)).endswith("/tabs.html") and s.page.url.endswith("/tabs.html")
        assert "closed tab 1" in await s.close_tab(1)
        with pytest.raises(ActionError, match="only tab"):
            await s.close_tab(0)
        with pytest.raises(ActionError, match="no tab 7"):
            await s.switch_tab(7)


async def test_a_link_to_another_site_does_not_leave_a_tab_behind(portal):
    async with open_session(portal + "/tabs.html") as s:
        await s.goto(portal + "/tabs.html")
        tree, _ = await s.snapshot()
        await s.click(ref_of(tree, r'link "Open an outside site"'))
        await s.page.wait_for_timeout(500)
        assert len(s.tabs()) == 1 and s.page.url.endswith("/tabs.html")


async def test_find_locates_elements_by_words_including_folded_rows(portal):
    async with open_session(portal + "/records.html") as s:
        await s.goto(portal + "/records.html")
        tree, _ = await s.snapshot()
        await s.select(ref_of(tree, r'combobox "Show entries"'), "50")
        await s.snapshot()
        assert 'button "Next"' in (await s.find("next"))
        assert "R033" in await s.find("R033")
        assert "nothing on the page matches" in await s.find("zzz-no-such-thing")


def test_find_puts_interactive_elements_first_and_honours_the_limit():
    tree = '- generic:\n  - paragraph: Search tips\n  - button "Search" [ref=e1]\n  - link "Search again" [ref=e2]\n  - text: search'
    found = find(tree, "search", limit=3)
    assert found[0].startswith("- button") and len(found) == 3
    assert find(tree, "") == []


async def test_javascript_tool_reads_values_as_json(portal):
    async with open_session(portal + "/records.html") as s:
        await s.goto(portal + "/records.html")
        assert await s.evaluate("document.title") == '"Records"'
        assert await s.evaluate("document.querySelectorAll('tbody tr').length") == "10"
        assert await s.evaluate("const rows = [...document.querySelectorAll('tbody tr')]; return rows.map(r => r.cells[0].innerText).slice(0, 2)") == '["R001", "R002"]'


@pytest.mark.parametrize("code, reason", [
    ("fetch('/data.json')", "network"),
    ("document.querySelector('button').click()", "triggers the page"),
    ("document.body.innerHTML = ''", "assigns to the page"),
    ("location.href = 'https://example.org'", "navigates"),
    ("localStorage.setItem('a', 'b')", "writes browser storage"),
    ("eval('1+1')", "run time"),
])
async def test_javascript_tool_refuses_code_that_is_not_read_only(portal, code, reason):
    async with open_session(portal + "/records.html") as s:
        await s.goto(portal + "/records.html")
        with pytest.raises(ActionError, match=reason):
            await s.evaluate(code)


async def test_javascript_tool_reports_script_errors_and_caps_long_output(portal):
    async with open_session(portal + "/records.html") as s:
        await s.goto(portal + "/records.html")
        with pytest.raises(ActionError, match="the script failed"):
            await s.evaluate("nothingHere.x")
        assert "more characters cut" in await s.evaluate("'x'.repeat(50000)", max_chars=100)


async def test_inspect_element_shows_the_real_html_behind_a_tree_element(portal):
    async with open_session(portal + "/records.html") as s:
        await s.goto(portal + "/records.html")
        tree, _ = await s.snapshot()
        info = await s.element_info(ref_of(tree, r"table"))
        assert info.startswith('<table id="t"') and "CSS selector: table#t" in info
        assert "11 <tr>" in info and "no role attribute in the HTML" in info  # a header row plus ten data rows


async def test_inspect_element_reports_a_role_that_is_written_in_the_html(portal):
    async with open_session(portal + "/scrollbox.html") as s:
        await s.goto(portal + "/scrollbox.html")
        tree, _ = await s.snapshot()
        assert 'role="region" is written in the HTML' in await s.element_info(ref_of(tree, r'region "Long list"'))
        with pytest.raises(ActionError, match="no element has the ref"):
            await s.element_info("e9999")


async def test_long_tool_output_says_it_was_cut(portal):
    from scoutskit.tools import Collector, build_registry

    async with open_session(portal + "/scrollbox.html") as s:
        await s.goto(portal + "/scrollbox.html")
        text, _ = await build_registry(s, Collector([], "")).call("javascript_tool", {"expression": "'y'.repeat(9000)"})
        assert "[output cut at 6,000 characters" in text
