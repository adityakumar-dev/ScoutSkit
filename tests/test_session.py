import re

import pytest

from scoutskit.browser import ActionError, open_session


def ref_of(tree: str, pattern: str) -> str:
    match = re.search(pattern + r'.*?\[ref=([A-Za-z0-9_-]+)\]', tree)
    assert match, f"{pattern!r} not found in tree:\n{tree}"
    return match.group(1)


async def test_hidden_menu_is_not_listed_until_opened(portal):
    async with open_session(portal + "/index.html") as s:
        await s.goto(portal + "/index.html")
        tree, labels = await s.snapshot()
        assert 'link "Records"' not in tree  # collapsed menu items are not offered to the agent
        assert any("Toggle navigation" in label for label in labels.values())
        await s.click(ref_of(tree, r'button "Toggle navigation"'))
        tree, _ = await s.snapshot()
        assert 'link "Records"' in tree


async def test_select_and_paginate(portal):
    async with open_session(portal + "/records.html") as s:
        await s.goto(portal + "/records.html")
        assert "Showing 1 to 10 of 40" in await s.text()
        tree, _ = await s.snapshot()
        await s.select(ref_of(tree, r'combobox "Show entries"'), "20")
        assert "Showing 1 to 20 of 40" in await s.text()
        tree, _ = await s.snapshot()
        await s.click(ref_of(tree, r'button "Next"'))
        assert "Showing 21 to 40 of 40" in await s.text()
        assert "R040" in await s.text()


async def test_network_bodies_and_console(portal):
    async with open_session(portal + "/index.html") as s:
        await s.goto(portal + "/index.html")
        await s.page.wait_for_function("document.getElementById('status').textContent.includes('loaded')")
        calls = s.network_log(r"data\.json")
        assert calls and calls[0].status == 200
        assert '"count": 40' in await s.network_body(calls[0].index)
        assert any("demo console error" in line for line in s.console_log(errors_only=True))


async def test_alert_does_not_block(portal):
    async with open_session(portal + "/index.html") as s:
        await s.goto(portal + "/index.html")
        tree, _ = await s.snapshot()
        await s.click(ref_of(tree, r'button "Show alert"'))
        assert any("hello from the portal" in line for line in s.console_log())
        assert "Demo Portal" in await s.text()  # the page is still usable


async def test_credential_and_personal_fields_are_refused(portal):
    async with open_session(portal + "/index.html") as s:
        await s.goto(portal + "/index.html")
        tree, _ = await s.snapshot()
        for label in ("Password", "Username"):
            with pytest.raises(ActionError, match="login or personal-data"):
                await s.fill(ref_of(tree, rf'textbox "{label}"'), "x")
        await s.fill(ref_of(tree, r'searchbox "Search records"'), "R001")  # an ordinary field still works


@pytest.mark.parametrize("url, expect", [
    ("https://example.org/", "outside"),
    ("file:///etc/passwd", "only http"),
    ("javascript:alert(1)", "only http"),
])
async def test_navigation_policy(portal, url, expect):
    async with open_session(portal + "/index.html") as s:
        with pytest.raises(ActionError, match=expect):
            await s.goto(url)


async def test_robots_txt_is_respected(portal):
    async with open_session(portal + "/index.html") as s:
        with pytest.raises(ActionError, match="robots.txt"):
            await s.goto(portal + "/private/secret.html")
    async with open_session(portal + "/index.html", respect_robots=False) as s:
        await s.goto(portal + "/private/secret.html")  # only reachable when robots is switched off explicitly


async def test_bad_refs_give_readable_errors(portal):
    async with open_session(portal + "/index.html") as s:
        await s.goto(portal + "/index.html")
        with pytest.raises(ActionError, match="not an element ref"):
            await s.click("../etc")
        with pytest.raises(ActionError, match="no element has the ref"):
            await s.click("e9999")


async def test_scroll_moves_the_container_not_the_page(portal):
    async with open_session(portal + "/scrollbox.html") as s:
        await s.goto(portal + "/scrollbox.html")
        tree, _ = await s.snapshot()
        report = await s.scroll("down", ref_of(tree, r'region "Long list"'))
        assert "position 0 ->" in report
        assert await s.page.evaluate("document.getElementById('box').scrollTop") > 0
        assert await s.page.evaluate("window.scrollY") == 0  # the page itself stayed put


async def test_scroll_without_a_ref_scrolls_the_page_and_says_when_the_end_is_reached(portal):
    async with open_session(portal + "/scrollbox.html") as s:
        await s.goto(portal + "/scrollbox.html")
        reports = [await s.scroll("down") for _ in range(8)]
        assert await s.page.evaluate("window.scrollY") > 0
        assert "cannot scroll down any further" in reports[-1]
        assert "scrolled down" in reports[0]


async def test_scroll_up_at_the_top_says_so(portal):
    async with open_session(portal + "/scrollbox.html") as s:
        await s.goto(portal + "/scrollbox.html")
        assert "already at the top" in await s.scroll("up")


async def test_the_agent_sees_a_folded_tree_and_read_page_unfolds_it(portal, monkeypatch):
    from scoutskit.browser import session as session_module

    monkeypatch.setattr(session_module, "TREE_BUDGET_CHARS", 700)
    async with open_session(portal + "/records.html") as s:
        await s.goto(portal + "/records.html")
        tree_, _ = await s.snapshot()
        await s.select(ref_of(tree_, r'combobox "Show entries"'), "50")  # all 40 rows on one page
        folded, _ = await s.snapshot()
        assert "more row items like the ones above" in folded and "R040" in folded and "R020" not in folded
        full, _ = await s.snapshot(full=True)
        assert "R020" in full
        table_ref = ref_of(full, r"table")
        part = await s.read_page(table_ref, full=True)
        assert part.startswith("[the part of the page under ref") and "R020" in part and "[ref=" in part
        assert "R020" in await s.visible_text()  # folded rows still count as being on the page (grounding)


async def test_stopping_a_session_while_its_browser_is_still_starting_leaves_nothing_behind():
    import asyncio

    async def job():
        async with open_session("about:blank"):
            await asyncio.sleep(60)

    for delay in (0, 0.05, 0.3):
        task = asyncio.create_task(job())
        await asyncio.sleep(delay)
        task.cancel()
        await asyncio.wait_for(asyncio.gather(task, return_exceptions=True), 30)
        leftovers = [t for t in asyncio.all_tasks() if t is not asyncio.current_task() and not t.done()]
        assert not leftovers, f"tasks still running after cancelling at {delay}s: {leftovers}"
