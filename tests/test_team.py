"""The main brain's team: sub-agents in parallel, the brain checks the first finished result, the rest are stopped."""

import asyncio
import json

from scoutskit import team as team_module
from scoutskit.brief import Brief
from scoutskit.browser import open_browser
from scoutskit.control import Decision, PlanGate
from scoutskit.provider.llm import LLMResult
from scoutskit.recorder import RunRecorder
from scoutskit.search import Hit
from scoutskit.team import Team, team_picks
from test_agent_loop import ScriptedChat, plan


def downloader_and_waiter():
    """On the downloads page: save the report, then done. Anywhere else: keep waiting. Each sub-agent gets its own memory."""
    def model():
        saved = []

        async def brain(page: str) -> dict:
            if "Download report" in page:
                if saved:
                    return {"tool": "done", "args": {}}
                saved.append(True)
                return {"tool": "save_file", "args": {"url": "report.pdf"}}
            return {"tool": "wait_for", "args": {"seconds": 1}}
        return [ScriptedChat(brain=brain)]
    return model


def brief_for(portal, *pages, agents=2):
    hits = [Hit(page, f"{portal}/{page}", "", "duckduckgo") for page in pages]
    return Brief(task="get the report", understanding="u", plan=plan(start_url=hits[0].url, min_items=1, item_name="report"),
                 sources=hits, picks=[(h, "why") for h in hits], steps=[], agents=agents)


def verdict(complete, why="checked"):
    async def complete_json(provider, system, user):
        assert "report.pdf" in user  # the brain sees the files the sub-agent saved
        return LLMResult({"complete": complete, "why": why}, 1, 1, 1)
    return complete_json


def events(recorder):
    return [json.loads(line) for line in (recorder.dir / "actions.jsonl").read_text().splitlines()]


async def test_the_first_verified_result_wins_and_the_other_sub_agent_is_stopped(portal, tmp_path, monkeypatch):
    monkeypatch.setattr(team_module, "complete_json", verdict(True))
    recorder = RunRecorder(tmp_path)
    async with open_browser() as host:
        team = Team(host, brief_for(portal, "files.html", "typing.html"), "get the report", providers=[type("P", (), {"name": "scripted"})()],
                    make_models=downloader_and_waiter(), recorder=recorder, max_steps=30, web=False)
        result = await team.run()
    assert result.winner.id == "a1" and result.verdict == "checked"
    assert (recorder.files_dir / "report.pdf").exists()
    log = events(recorder)
    assert {(e["agent"], e["status"]) for e in log if e.get("event") == "agent"} >= {("a1", "running"), ("a1", "done"), ("a2", "running"), ("a2", "stopped")}
    assert any(e.get("event") == "file" and e["agent"] == "a1" for e in log)
    assert all(e.get("agent") in ("a1", "a2") for e in log if "tool" in e)  # every step says which sub-agent took it


async def test_a_result_the_brain_rejects_does_not_win(portal, tmp_path, monkeypatch):
    monkeypatch.setattr(team_module, "complete_json", verdict(False, "only part of it"))
    recorder = RunRecorder(tmp_path)
    async with open_browser() as host:
        team = Team(host, brief_for(portal, "files.html", agents=1), "get the report", providers=[type("P", (), {"name": "scripted"})()],
                    make_models=downloader_and_waiter(), recorder=recorder, max_steps=5, web=False)
        result = await team.run()
    assert result.winner is None and result.verdict == "only part of it" and result.best.id == "a1"


async def test_when_not_autonomous_the_person_accepts_the_result(portal, tmp_path, monkeypatch):
    monkeypatch.setattr(team_module, "complete_json", verdict(True))
    recorder, topics = RunRecorder(tmp_path), []
    gate = PlanGate(announce=lambda state, topic: topics.append((state, topic)))

    async def accept_when_asked():
        while not gate.waiting:
            await asyncio.sleep(0.05)
        gate.answer(Decision(True))

    async with open_browser() as host:
        team = Team(host, brief_for(portal, "files.html", agents=1), "get the report", providers=[type("P", (), {"name": "scripted"})()],
                    make_models=downloader_and_waiter(), recorder=recorder, max_steps=5, web=False, gate=gate)
        result, _ = await asyncio.gather(team.run(), accept_when_asked())
    assert result.winner.id == "a1" and topics == [("waiting", "result"), ("approved", "result")]
    check = next(e for e in events(recorder) if e.get("event") == "result_check")
    assert check["files"] == ["report.pdf"] and check["name"] == "Main agent"


def test_picks_are_distinct_and_capped():
    hits = [Hit("a", "https://a.example/x", "", "d"), Hit("a again", "http://www.a.example/x/", "", "d")] + [Hit(str(n), f"https://{n}.example", "", "d") for n in range(5)]
    brief = Brief(task="t", understanding="u", plan=plan(start_url=hits[0].url), sources=hits, picks=[(h, "") for h in hits], steps=[])
    assert [h.url for h in team_picks(brief, 9)] == ["https://a.example/x", "https://0.example", "https://1.example"]
    assert len(team_picks(brief, 0)) == 1


async def test_a_pick_that_will_not_open_hands_over_to_the_next_pick(portal, tmp_path, monkeypatch):
    monkeypatch.setattr(team_module, "complete_json", verdict(True))
    dead = Hit("dead site", "http://127.0.0.1:9/", "", "wikidata")  # nothing listens there: the start page cannot be opened
    live = Hit("downloads", f"{portal}/files.html", "", "web")
    brief = Brief(task="get the report", understanding="u", plan=plan(start_url=dead.url, min_items=1, item_name="report"),
                  sources=[dead, live], picks=[(dead, "official?"), (live, "backup")], steps=[], agents=1)
    recorder, said = RunRecorder(tmp_path), []
    async with open_browser() as host:
        team = Team(host, brief, "get the report", providers=[type("P", (), {"name": "scripted"})()], make_models=downloader_and_waiter(),
                    recorder=recorder, max_steps=6, web=False, say=said.append)
        result = await team.run()
    assert [m.id for m in result.members] == ["a1", "a2"] and result.winner.id == "a2"
    assert any("did not deliver" in line and live.url in line for line in said)
    statuses = [(e["agent"], e["status"]) for e in events(recorder) if e.get("event") == "agent"]
    assert ("a1", "failed") in statuses and ("a2", "done") in statuses


async def test_a_scout_that_picked_up_a_file_but_did_not_deliver_still_hands_over_to_the_next_source(portal, tmp_path, monkeypatch):
    """Saved on the way, not the answer: a file from its starting pick must not stop the team from trying the remaining sources."""
    monkeypatch.setattr(team_module, "complete_json", verdict(True))
    unrelated = Hit("a spreadsheet", f"{portal}/report.pdf", "", "web")  # saved at once as a file; the agent then starts on the site's home page
    good = Hit("downloads", f"{portal}/files.html", "", "web")
    brief = Brief(task="get the report", understanding="u", plan=plan(start_url=unrelated.url, min_items=2, item_name="report"),
                  sources=[unrelated, good], picks=[(unrelated, ""), (good, "")], steps=[], agents=1)
    calls = []

    def model():
        mine = iter("abcdefghijklmnopqrstuvwxyz")

        async def brain(page: str) -> dict:
            calls.append(page)
            if "Download report" in page:
                return {"tool": "done", "args": {}} if "FILES SAVED FOR THE USER: report" in page else {"tool": "save_file", "args": {"url": "report.pdf", "name": "second.pdf"}}
            return {"tool": "press", "args": {"key": next(mine)}}
        return [ScriptedChat(brain=brain)]

    recorder = RunRecorder(tmp_path)
    async with open_browser() as host:
        team = Team(host, brief, "get the report", providers=[type("P", (), {"name": "scripted"})()], make_models=model, recorder=recorder, max_steps=6, web=False)
        result = await team.run()
    first = result.members[0]
    assert len(first.files) == 1 and first.result.status != "completed"  # it did pick something up
    assert [m.id for m in result.members][:2] == ["a1", "a2"]  # and the next source was still tried


def test_fallbacks_come_from_the_other_search_results_and_fresh_sites_are_tried_before_failed_ones():
    from scoutskit.team import fallback_sources, order_spares

    picks = [Hit("official", "https://sih.gov.in/ps", "", "web")]
    others = [Hit("same again", "http://www.sih.gov.in/ps/", "", "web"), Hit("encyclopaedia", "https://en.wikipedia.org/wiki/SIH", "", "wikipedia"),
              Hit("mirror", "https://mirror.example/ps", "", "web"), Hit("photo", "https://x.example/a.png", "", "web"), Hit("news", "https://news.example/sih", "", "web")]
    brief = Brief(task="t", understanding="u", plan=plan(start_url=picks[0].url), sources=picks + others, picks=[(picks[0], "")], steps=[])
    extras = fallback_sources(brief, picks)
    assert [h.title for h in extras] == ["mirror", "news"]  # no duplicate of a pick, no article, no picture

    spares = [Hit("a", "https://sih.gov.in/other", "", "web"), *extras]
    assert [h.title for h in order_spares(spares, {"sih.gov.in": 1}, set())] == ["mirror", "news", "a"]  # a site that failed once goes last
    assert [h.title for h in order_spares(spares, {"sih.gov.in": 2}, set())] == ["mirror", "news"]  # twice: not again
    assert [h.title for h in order_spares(spares, {}, {"mirror.example"})] == ["a", "news"]  # refused: never


async def test_with_a_person_in_the_loop_a_result_the_brain_doubts_is_shown_to_them_with_the_doubt(portal, tmp_path, monkeypatch):
    monkeypatch.setattr(team_module, "complete_json", verdict(False, "cannot confirm it is the whole list"))
    recorder, topics = RunRecorder(tmp_path), []
    gate = PlanGate(announce=lambda state, topic: topics.append((state, topic)))

    async def accept_anyway():
        while not gate.waiting:
            await asyncio.sleep(0.05)
        gate.answer(Decision(True))

    async with open_browser() as host:
        team = Team(host, brief_for(portal, "files.html", agents=1), "get the report", providers=[type("P", (), {"name": "scripted"})()],
                    make_models=downloader_and_waiter(), recorder=recorder, max_steps=5, web=False, gate=gate)
        result, _ = await asyncio.gather(team.run(), accept_anyway())
    assert result.winner is not None and topics == [("waiting", "result"), ("approved", "result")]
    check = next(e for e in events(recorder) if e.get("event") == "result_check")
    assert check["doubt"] is True and "whole list" in check["why"]  # the person decided, knowing the brain's doubt


async def test_the_brain_decides_alone_in_autonomous_mode(portal, tmp_path, monkeypatch):
    monkeypatch.setattr(team_module, "complete_json", verdict(False, "only part of it"))
    recorder = RunRecorder(tmp_path)
    async with open_browser() as host:
        team = Team(host, brief_for(portal, "files.html", agents=1), "get the report", providers=[type("P", (), {"name": "scripted"})()],
                    make_models=downloader_and_waiter(), recorder=recorder, max_steps=5, web=False)  # no gate
        result = await team.run()
    assert result.winner is None and result.verdict == "only part of it"


async def test_a_result_that_matches_the_pages_own_total_is_only_checked_for_relevance(monkeypatch):
    """Counting settles completeness; the brain is asked only whether these are the right kind of items, never about the site."""
    asked = []

    async def judge(provider, system, user):
        asked.append(system)
        return LLMResult({"relevant": True, "why": "they are the problem statements asked for"}, 1, 1, 1)

    monkeypatch.setattr(team_module, "complete_json", judge)
    rows = [{"id": str(n), "title": f"item {n}"} for n in range(101)]
    member = team_module.Member("a1", "Main agent", Hit("mirror", "https://mirror.example/", "", "web"))
    member.result = type("R", (), {"rows": rows, "fields": ["id", "title"], "message": "", "status": "completed"})()
    member.session = type("S", (), {"stated_total": staticmethod(lambda: _async(101)), "repeats": staticmethod(lambda: _async(None)),
                                    "page": type("Pg", (), {"url": "https://mirror.example/"})()})()
    team = Team.__new__(Team)
    team.task, team.providers, team.brief = "find all the sih 2025 ps", [type("P", (), {"name": "p"})()], type("B", (), {"plan": type("Pl", (), {"goal": "g"})()})()
    ok, why = await team._verify(member)
    assert ok and "exactly the total the page states" in why
    assert len(asked) == 1 and "ONE thing" in asked[0] and "Do NOT judge which website" in asked[0]  # the narrow question, not the open verdict

    member.result.rows = rows[:40]  # the count does not match: the open check (with its facts) applies
    asked.clear()
    monkeypatch.setattr(team_module, "complete_json", lambda *a: _async(LLMResult({"complete": False, "why": "only 40 of 101"}, 1, 1, 1)))
    ok, why = await team._verify(member)
    assert not ok and why == "only 40 of 101"


async def _async(value):
    return value
