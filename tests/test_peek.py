"""A first look at each candidate source: pages that hold a list go first, empty shells last, and the order is kept among equals."""

import pytest

from scoutskit.browser import open_browser
from scoutskit.peek import Peek, peek, rank
from scoutskit.search import Hit


def test_the_rank_says_which_sources_to_try_first():
    assert Peek("u", items=101).rank == 0 and Peek("u", items=5).rank == 0
    assert Peek("u").rank == 1 and Peek("u", items=3).rank == 1 and Peek("u", error="slow").rank == 1  # nothing to go on: neutral
    assert Peek("u", empty=True).rank == 2 and Peek("u", stated=0).rank == 2
    assert Peek("u", items=20, empty=True).rank == 0  # a list on the page wins over wording elsewhere on it


async def test_a_page_with_a_list_a_page_without_and_a_page_that_will_not_open(portal):
    async with open_browser() as host:
        with_list = await peek(host, Hit("cards", f"{portal}/cards.html", "", "web"))
        none = await peek(host, Hit("form", f"{portal}/typing.html", "", "web"))
        dead = await peek(host, Hit("dead", "http://127.0.0.1:9/", "", "web"))
    assert with_list.items == 30 and with_list.rank == 0
    assert none.items == 0 and none.rank == 1
    assert dead.error and dead.rank == 1  # could not look: neither good nor bad


async def test_ranking_puts_the_page_with_data_first_and_keeps_the_rest_in_order(portal):
    hits = [Hit("form", f"{portal}/typing.html", "", "web"), Hit("cards", f"{portal}/cards.html", "", "web"), Hit("dead", "http://127.0.0.1:9/", "", "web")]
    async with open_browser() as host:
        ordered, seen = await rank(host, hits)
    assert [h.title for h in ordered] == ["cards", "form", "dead"]  # list first; the other two keep their order
    assert {p.url: p.rank for p in seen}[hits[1].url] == 0


async def test_the_team_starts_from_the_source_that_holds_data_not_from_the_first_one_the_brain_listed(portal, tmp_path):
    import json

    from scoutskit.brief import Brief
    from scoutskit.recorder import RunRecorder
    from scoutskit.team import Team
    from test_agent_loop import ScriptedChat, plan

    first, better = Hit("official", f"{portal}/typing.html", "", "web"), Hit("mirror", f"{portal}/cards.html", "", "web")
    brief = Brief(task="t", understanding="u", plan=plan(start_url=first.url, min_items=1), sources=[first, better], picks=[(first, "official"), (better, "mirror")], steps=[], agents=1)

    async def brain(page: str) -> dict:
        return {"tool": "fail", "args": {"reason": "just looking"}}

    recorder = RunRecorder(tmp_path)
    async with open_browser() as host:
        team = Team(host, brief, "t", providers=[type("P", (), {"name": "scripted"})()], make_models=lambda: [ScriptedChat(brain=brain)], recorder=recorder,
                    max_steps=3, web=False, peek=True)
        await team.run()
    log = [json.loads(line) for line in (recorder.dir / "actions.jsonl").read_text().splitlines()]
    started = [e["url"] for e in log if e.get("event") == "agent" and e.get("status") == "running"]
    assert started[0].endswith("/cards.html")  # the page with the list went first
    assert {e["url"].rsplit("/", 1)[1]: e["rank"] for e in log if e.get("event") == "peek"} == {"typing.html": 1, "cards.html": 0}


def test_among_pages_with_a_list_the_one_that_matches_its_own_total_goes_first():
    news, data = Peek("news", items=36), Peek("data", items=101, stated=101)
    assert data.order < news.order and Peek("u", items=20, stated=50).order == news.order  # a length that matches no stated total is only "some list"
    assert Peek("u", empty=True).order[0] == 2
