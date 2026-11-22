"""find_links: the real addresses behind hidden menus and table rows, so the agent never has to guess one."""

import pytest

from scoutskit.browser import open_session
from scoutskit.browser.links import rank, words
from scoutskit.tools import Collector, build_registry


def test_words_drop_filler_and_ranking_prefers_text_over_context_and_a_document_link():
    assert words("download the B.Tech Syllabus pdf") == ["tech", "syllabus"]
    links = [
        {"text": "Home", "href": "https://x.example/", "context": "Home", "shown": True},
        {"text": "Syllabus", "href": "https://x.example/syllabus", "context": "Syllabus", "shown": False},
        {"text": "Click here", "href": "https://x.example/btech_cse.pdf", "context": "B.Tech Computer Science syllabus Click here", "shown": True},
    ]
    found = rank(links, "btech computer science syllabus")
    assert [l.href for l in found][0] == "https://x.example/btech_cse.pdf" and len(found) == 2  # the row names it best, and it is a document
    assert rank(links, "zzz nothing") == []


async def test_a_link_in_a_hidden_dropdown_is_found_with_its_real_address_and_a_row_link_with_its_row(portal):
    async with open_session(portal + "/menu_site.html") as session:
        await session.goto(portal + "/menu_site.html")
        registry = build_registry(session, Collector([]))
        tree_says, _ = await registry.call("find", {"query": "Syllabus"})
        assert "nothing on the page matches" in tree_says  # the tree cannot see the closed dropdown
        out, is_read = await registry.call("find_links", {"query": "syllabus"})
        assert is_read and f"{portal}/syllabus.html" in out and "hidden in a menu" in out
        row, _ = await registry.call("find_links", {"query": "B.Tech computer science"})
        assert f"{portal}/report.pdf" in row and "around it: B.Tech Computer Science and Engineering" in row  # which row the link belongs to
        none, _ = await registry.call("find_links", {"query": "quantum cooking"})
        assert "no link on this page matches" in none
