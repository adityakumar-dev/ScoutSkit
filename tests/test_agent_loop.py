"""The agent graph end to end against the local portal, with a scripted chat model instead of an LLM.

If these pass, the graph, tools, collector and done-validator work; what remains for a real
model is judgment, which is measured separately (benchmarks).
"""

import json
import re
import uuid
from typing import Any

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.outputs import ChatGeneration, ChatResult

from scoutskit.agent import Agent, TaskPlan
from scoutskit.browser import open_session
from scoutskit.recorder import RunRecorder


class ScriptedChat(BaseChatModel):
    """A chat model whose decisions come from a function; it makes real native tool calls."""

    brain: Any

    @property
    def _llm_type(self) -> str:
        return "scripted"

    def bind_tools(self, tools, **kwargs):
        return self

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        raise NotImplementedError

    async def _agenerate(self, messages, stop=None, run_manager=None, **kwargs):
        page = [m for m in messages if isinstance(m, HumanMessage)][-1].content
        decision = await self.brain(page)
        calls = [{"name": decision["tool"], "args": decision.get("args", {}), "id": f"call_{uuid.uuid4().hex[:8]}"}] if decision.get("tool") else []
        return ChatResult(generations=[ChatGeneration(message=AIMessage(content=decision.get("thought", ""), tool_calls=calls))])


def ref(tree: str, pattern: str) -> str | None:
    match = re.search(pattern + r".*?\[ref=([A-Za-z0-9_-]+)\]", tree)
    return match.group(1) if match else None


def table_rows(tree: str) -> list[dict]:
    rows, current = [], None
    for line in tree.splitlines():
        if re.match(r"\s*- row\b", line):
            current = []
            rows.append(current)
        elif current is not None and (cell := re.match(r'\s*- cell "([^"]*)"', line)):
            current.append(cell.group(1))
    return [dict(zip(("id", "title", "category"), r)) for r in rows if len(r) == 3]


class CompetentBrain:
    """What a good model would do on this portal: open the menu, go to Records, read every page."""

    def __init__(self) -> None:
        self.extracted: set[str] = set()

    async def __call__(self, page: str) -> dict:
        tree = page.split("TREE:\n", 1)[1]
        on_records = "records.html" in page.split("CURRENT PAGE:", 1)[1].split("\n", 1)[0]
        if not on_records:
            if link := ref(tree, r'link "Records"'):
                return {"tool": "click", "args": {"ref": link}}
            return {"tool": "click", "args": {"ref": ref(tree, r'button "Toggle navigation"')}}
        rows = table_rows(tree)
        if rows and any(r["id"] not in self.extracted for r in rows):
            self.extracted.update(r["id"] for r in rows)
            return {"tool": "extract_rows", "args": {"rows": rows}}
        if 'button "Next" [disabled]' not in tree:
            return {"tool": "click", "args": {"ref": ref(tree, r'button "Next"')}}
        return {"tool": "done", "args": {}}


def plan(**overrides) -> TaskPlan:
    base = dict(start_url="", goal="extract all records", item_name="record", fields=[], key_field="", min_items=40)
    return TaskPlan(**{**base, **overrides})


async def run_agent(portal, tmp_path, brain, **plan_overrides):
    start = portal + "/index.html"
    async with open_session(start) as session:
        recorder = RunRecorder(tmp_path)
        agent = Agent(session, [ScriptedChat(brain=brain)], ["scripted"], recorder, max_steps=20)
        result = await agent.run("extract all records", plan(start_url=start, **plan_overrides))
    return result, recorder


async def test_agent_collects_every_record(portal, tmp_path):
    result, recorder = await run_agent(portal, tmp_path, CompetentBrain())
    assert result.status == "completed", result.message
    assert result.fields == ["id", "title", "category"]  # the page's own columns, none invented
    assert sorted(r["id"] for r in result.rows) == [f"R{i:03d}" for i in range(1, 41)]
    log = [json.loads(line) for line in (recorder.dir / "actions.jsonl").read_text().splitlines()]
    steps = [e for e in log if "step" in e]
    assert all(e["ok"] for e in steps), [e["error"] for e in steps if not e["ok"]]
    assert (recorder.dir / "screenshots" / "step01.png").exists()


async def test_done_is_rejected_until_enough_items_are_collected(portal, tmp_path):
    async def impatient(page):
        return {"thought": "finished", "tool": "done", "args": {}}

    result, _ = await run_agent(portal, tmp_path, impatient)
    assert result.status == "incomplete" and not result.rows
    assert "expected at least 40" in result.message


async def test_reply_without_a_tool_gets_a_clear_correction(portal, tmp_path):
    feedback_seen = []

    async def forgetful(page):
        feedback_seen.append(page.split("FEEDBACK FROM LAST STEP: ", 1)[1].split("\n", 1)[0])
        return {"thought": "hmm"} if len(feedback_seen) == 1 else {"tool": "fail", "args": {"reason": "test"}}

    result, _ = await run_agent(portal, tmp_path, forgetful)
    assert "without calling a tool" in feedback_seen[1]
    assert result.status == "failed" and result.message == "test"


async def test_bad_tool_arguments_are_reported_back_not_fatal(portal, tmp_path):
    calls = []

    async def clumsy(page):
        calls.append(page.split("FEEDBACK FROM LAST STEP: ", 1)[1].split("\n", 1)[0])
        if len(calls) == 1:
            return {"tool": "page_text", "args": {"max_charts": 10}}  # a misspelled argument
        return {"tool": "fail", "args": {"reason": "stop"}}

    result, _ = await run_agent(portal, tmp_path, clumsy)
    assert calls[1] != "none"  # the model was told what went wrong
    assert result.status == "failed"


class ReasonableBrain(CompetentBrain):
    """Collects everything, then asks to finish; when refused it states why there are no more items."""

    def __init__(self) -> None:
        super().__init__()
        self.done_calls = 0

    async def __call__(self, page: str) -> dict:
        decision = await super().__call__(page)
        if decision["tool"] == "done":
            self.done_calls += 1
            if self.done_calls >= 2:
                decision["args"] = {"reason": "the page shows 40 of 40 entries"}
        return decision


async def test_done_with_a_reason_overrides_a_wrong_expected_count(portal, tmp_path):
    result, recorder = await run_agent(portal, tmp_path, ReasonableBrain(), min_items=100)  # the planner guessed 100; the site has 40
    assert result.status == "completed" and len(result.rows) == 40
    assert "warning" in result.message and "40 of 40 entries" in result.message
    log = [json.loads(line) for line in (recorder.dir / "actions.jsonl").read_text().splitlines()]
    refused = next(e for e in log if e.get("tool") == "done" and not e["ok"])
    assert "call done again with a `reason`" in refused["error"]


async def test_a_reason_cannot_override_the_total_the_page_states(portal, tmp_path):
    seen_pages, state = [], {"extracted": False, "done_attempts": 0}

    async def hasty(page: str) -> dict:
        seen_pages.append(page)
        tree = page.split("TREE:\n", 1)[1]
        if "records.html" not in page.split("CURRENT PAGE:", 1)[1].split("\n", 1)[0]:
            if link := ref(tree, r'link "Records"'):
                return {"tool": "click", "args": {"ref": link}}
            return {"tool": "click", "args": {"ref": ref(tree, r'button "Toggle navigation"')}}
        if not state["extracted"]:
            state["extracted"] = True
            return {"tool": "extract_rows", "args": {"rows": table_rows(tree)}}  # page 1 of 4 only
        if state["done_attempts"] == 0:
            state["done_attempts"] += 1
            return {"tool": "done", "args": {"reason": "that is everything on the page"}}
        return {"tool": "fail", "args": {"reason": "stop"}}

    result, recorder = await run_agent(portal, tmp_path, hasty, min_items=5)
    assert len(result.rows) == 10
    assert any("THE PAGE STATES A TOTAL OF 40 ENTRIES" in page for page in seen_pages)  # the evidence is shown to the model
    log = [json.loads(line) for line in (recorder.dir / "actions.jsonl").read_text().splitlines()]
    refused = next(e for e in log if e.get("tool") == "done")
    assert not refused["ok"] and "the page states 40 entries and you have collected 10" in refused["error"]
    assert "Collect the rest first" in refused["error"] and "only if the task asks for a subset" in refused["error"].lower()
