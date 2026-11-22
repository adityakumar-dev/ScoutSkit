"""A shared token budget, shorter leashes for replacement scouts, and open web for plans that start on several sites."""

import pytest

from scoutskit import team as team_module
from scoutskit.agent import Agent
from scoutskit.brief import Brief
from scoutskit.budget import Budget
from scoutskit.browser import open_browser, open_session
from scoutskit.provider.llm import LLMResult
from scoutskit.recorder import RunRecorder
from scoutskit.search import Hit
from scoutskit.team import SPARE_STEPS, Team
from test_agent_loop import ScriptedChat, plan
from test_team import events


def test_the_budget_counts_what_is_spent_and_zero_means_no_limit():
    budget = Budget(100)
    budget.spend(60)
    assert not budget.exhausted
    budget.spend(40)
    budget.spend(-5)  # never negative
    assert budget.exhausted and budget.spent == 100
    unlimited = Budget(0)
    unlimited.spend(10**9)
    assert not unlimited.exhausted


async def test_an_agent_stops_when_the_shared_budget_is_used_up(portal, tmp_path):
    class Costly(ScriptedChat):
        async def _agenerate(self, messages, stop=None, run_manager=None, **kwargs):
            result = await super()._agenerate(messages, stop, run_manager, **kwargs)
            result.generations[0].message.usage_metadata = {"input_tokens": 400, "output_tokens": 100, "total_tokens": 500}
            return result

    async def brain(page: str) -> dict:
        return {"tool": "wait_for", "args": {"seconds": 0}}

    budget = Budget(1200)
    async with open_session(portal + "/index.html") as session:
        agent = Agent(session, [Costly(brain=brain)], ["scripted"], RunRecorder(tmp_path), max_steps=30, budget=budget)
        result = await agent.run("wait", plan(start_url=portal + "/index.html", min_items=1))
    assert result.status == "max_budget" and "1,200" in result.message
    assert 1200 <= budget.spent < 2500 and result.steps <= 4  # it stopped within a step or two of the limit, not at the step limit


async def test_replacement_scouts_get_a_shorter_leash_and_no_replacement_starts_once_the_budget_is_gone(portal, tmp_path, monkeypatch):
    async def verified(provider, system, user):
        return LLMResult({"complete": True, "why": "x"}, 1, 1, 1)

    monkeypatch.setattr(team_module, "complete_json", verified)
    dead = Hit("dead", "http://127.0.0.1:9/", "", "web")
    spare = Hit("spare", f"{portal}/index.html", "", "web")
    brief = Brief(task="t", understanding="u", plan=plan(start_url=dead.url, min_items=1), sources=[dead, spare], picks=[(dead, ""), (spare, "")], steps=[], agents=1)
    steps_allowed = []

    class Probe(ScriptedChat):
        pass

    keys = iter("abcdefghijklmnopqrstuvwxyz")

    async def brain(page: str) -> dict:
        return {"tool": "press", "args": {"key": next(keys)}}  # a different action each time (not a loop), and not a read: it counts as acting

    recorder = RunRecorder(tmp_path)
    async with open_browser() as host:
        team = Team(host, brief, "t", providers=[type("P", (), {"name": "scripted"})()], make_models=lambda: [Probe(brain=brain)], recorder=recorder,
                    max_steps=60, web=False, budget=Budget(0))
        result = await team.run()
    spare_member = next(m for m in result.members if m.spare)
    assert spare_member.result.steps == SPARE_STEPS  # the replacement stopped at its own shorter limit, not at 60

    # with the budget already gone, nothing replaces the failed scout
    exhausted = Budget(1)
    exhausted.spend(5)
    recorder = RunRecorder(tmp_path)
    async with open_browser() as host:
        team = Team(host, brief, "t", providers=[type("P", (), {"name": "scripted"})()], make_models=lambda: [Probe(brain=brain)], recorder=recorder,
                    max_steps=60, web=False, budget=exhausted)
        result = await team.run()
    assert [m.id for m in result.members] == ["a1"] and "token budget" in result.verdict


def test_a_share_counts_against_both_and_either_running_out_stops_it():
    from scoutskit.budget import Share

    total = Budget(1000)
    first, second = Share(total, 300), Share(total, 300)
    first.spend(300)
    assert first.exhausted and not second.exhausted and total.spent == 300  # its own share is gone, the rest is not
    second.spend(100)
    total.spend(600)
    assert second.exhausted  # the whole budget is gone, whatever share is left


async def test_a_scout_that_only_reads_a_page_with_no_data_gives_up_and_the_next_source_takes_over(portal, tmp_path, monkeypatch):
    async def verified(provider, system, user):
        return LLMResult({"complete": True, "why": "the file"}, 1, 1, 1)

    monkeypatch.setattr(team_module, "complete_json", verified)
    empty = Hit("empty page", f"{portal}/typing.html", "", "web")  # a page that has nothing to collect
    good = Hit("downloads", f"{portal}/files.html", "", "web")
    brief = Brief(task="get the report", understanding="u", plan=plan(start_url=empty.url, min_items=1, item_name="report"),
                  sources=[empty, good], picks=[(empty, "official"), (good, "mirror")], steps=[], agents=1)
    prompts = []

    def model():
        count = iter(range(1, 10_000))
        saved = []

        async def brain(page: str) -> dict:
            prompts.append(page)
            if "Download report" in page:
                if saved:
                    return {"tool": "done", "args": {}}
                saved.append(True)
                return {"tool": "save_file", "args": {"url": "report.pdf"}}
            return {"tool": "grep_source", "args": {"pattern": f"data{next(count)}"}}  # reads and reads, a different pattern each time
        return [ScriptedChat(brain=brain)]

    recorder, said = RunRecorder(tmp_path), []
    async with open_browser() as host:
        team = Team(host, brief, "get the report", providers=[type("P", (), {"name": "scripted"})()], make_models=model, recorder=recorder,
                    max_steps=60, web=False, say=said.append, budget=Budget(900_000))
        result = await team.run()
    first = result.members[0]
    assert first.result.status == "incomplete" and "read the same page" in first.result.message and first.result.steps == 11  # the first read only establishes the page
    assert any("only read this page" in p for p in prompts)  # told to decide before it was stopped
    assert result.winner is not None and result.winner.id == "a2" and (recorder.files_dir / "report.pdf").exists()


async def test_replacements_keep_coming_until_a_source_works_or_the_picks_run_out(portal, tmp_path, monkeypatch):
    async def verified(provider, system, user):
        return LLMResult({"complete": True, "why": "the file"}, 1, 1, 1)

    monkeypatch.setattr(team_module, "complete_json", verified)
    monkeypatch.setattr(team_module, "MAX_FAILURES_PER_HOST", 99)  # (the test pages all share one host)
    pages = ["typing.html", "details.html", "scrollbox.html", "files.html"]
    hits = [Hit(p, f"{portal}/{p}", "", "web") for p in pages]
    brief = Brief(task="get the report", understanding="u", plan=plan(start_url=hits[0].url, min_items=1, item_name="report"),
               sources=hits, picks=[(h, "") for h in hits], steps=[], agents=1)

    def model():
        count = iter(range(1, 10_000))
        saved = []

        async def brain(page: str) -> dict:
            if "Download report" in page:
                if saved:
                    return {"tool": "done", "args": {}}
                saved.append(True)
                return {"tool": "save_file", "args": {"url": "report.pdf"}}
            return {"tool": "wait_for", "args": {"seconds": next(count) / 1000}}  # different each time, never collects
        return [ScriptedChat(brain=brain)]

    recorder, said = RunRecorder(tmp_path), []
    async with open_browser() as host:
        team = Team(host, brief, "get the report", providers=[type("P", (), {"name": "scripted"})()], make_models=model, recorder=recorder,
                    max_steps=40, web=False, say=said.append, budget=Budget(900_000))
        result = await team.run()
    assert [m.id for m in result.members] == ["a1", "a2", "a3", "a4"], said
    assert result.winner is not None and result.winner.id == "a4"
