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

    counter = iter(range(1, 1000))

    async def brain(page: str) -> dict:
        return {"tool": "wait_for", "args": {"seconds": next(counter) / 1000}}  # a different call each time: not a loop

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
