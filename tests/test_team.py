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
    assert any("found nothing" in line and live.url in line for line in said)
    statuses = [(e["agent"], e["status"]) for e in events(recorder) if e.get("event") == "agent"]
    assert ("a1", "failed") in statuses and ("a2", "done") in statuses
