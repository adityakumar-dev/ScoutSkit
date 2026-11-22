"""Take-over: who drives the browser, the agent pausing between steps, and the inputs a person may send."""

import asyncio
import json

import pytest
from pydantic import ValidationError

from scoutskit.agent import Agent
from scoutskit.browser import ActionError, open_session
from scoutskit.control import RunControl
from scoutskit.recorder import RunRecorder
from scoutskit.server import remote_input
from scoutskit.server.tabs import TabWatcher
from test_agent_loop import ScriptedChat, plan


async def test_a_take_over_is_granted_at_the_next_checkpoint_and_the_agent_waits_until_it_is_handed_back():
    modes = []
    control = RunControl(announce=modes.append)
    assert await control.checkpoint() is False  # nobody asked: the agent just carries on
    control.request_user()
    assert control.mode == "requested" and not control.user_driving
    waiting = asyncio.create_task(control.checkpoint())
    await asyncio.sleep(0.05)
    assert control.user_driving and not waiting.done()  # the agent is paused
    control.release()
    assert await waiting is True and control.mode == "agent"
    assert modes == ["requested", "user", "agent"]


async def test_a_request_can_be_withdrawn_before_the_agent_reaches_a_checkpoint():
    control = RunControl()
    control.request_user()
    control.release()
    assert await control.checkpoint() is False


async def test_a_forgotten_take_over_ends_by_itself():
    control = RunControl(limit_s=0.1)
    control.request_user()
    assert await control.checkpoint() is True and control.mode == "agent"


async def test_the_agent_pauses_for_a_person_and_is_told_afterwards_that_the_page_may_have_changed(portal, tmp_path):
    start = portal + "/index.html"
    control = RunControl()
    prompts = []

    async def brain(page: str) -> dict:
        prompts.append(page)
        if len(prompts) == 1:
            control.request_user()  # the person asks while the agent is deciding; the agent's next look is the checkpoint
            return {"tool": "scroll", "args": {"direction": "down"}}
        return {"tool": "fail", "args": {"reason": "stop"}}

    async with open_session(start) as session:
        agent = Agent(session, [ScriptedChat(brain=brain)], ["scripted"], RunRecorder(tmp_path), max_steps=5, control=control)
        run = asyncio.create_task(agent.run("anything", plan(start_url=start)))
        await asyncio.sleep(2)
        assert control.user_driving and len(prompts) == 1 and not run.done()  # paused, no second decision yet
        control.release()
        await asyncio.wait_for(run, 20)
    assert len(prompts) == 2
    assert "A PERSON USED THE BROWSER WHILE YOU WERE PAUSED" in prompts[1] and "A PERSON USED THE BROWSER" not in prompts[0]


def test_only_the_allowed_inputs_parse():
    assert remote_input.parse({"kind": "click", "x": 0.5, "y": 0.25}).x == 0.5
    assert remote_input.parse({"kind": "key", "key": "Enter"}).key == "Enter"
    for bad in ({"kind": "click", "x": 2, "y": 0}, {"kind": "key", "key": "F12"}, {"kind": "type", "text": ""},
                {"kind": "type", "text": "x" * 2001}, {"kind": "scroll", "x": 0, "y": 0, "dy": 99999}, {"kind": "eval", "code": "1"}, None):
        with pytest.raises(ValidationError):
            remote_input.parse(bad)


async def test_a_click_a_typed_word_and_a_key_reach_the_page_at_the_right_place(portal):
    async with open_session(portal + "/index.html") as session:
        await session.goto(portal + "/index.html")
        box = await session.page.get_by_role("searchbox").or_(session.page.get_by_role("textbox").first).first.bounding_box()
        size = session.page.viewport_size
        point = {"x": (box["x"] + box["width"] / 2) / size["width"], "y": (box["y"] + box["height"] / 2) / size["height"]}
        await remote_input.apply(session, remote_input.parse({"kind": "click", **point}))
        await remote_input.apply(session, remote_input.parse({"kind": "type", "text": "hello"}))
        await remote_input.apply(session, remote_input.parse({"kind": "key", "key": "Backspace"}))
        typed = await session.page.evaluate("document.activeElement.value")
        assert typed == "hell"
        await remote_input.apply(session, remote_input.parse({"kind": "scroll", "x": 0.5, "y": 0.5, "dy": 100}))


async def test_a_person_can_use_the_browser_tools(portal):
    async with open_session(portal + "/typing.html") as session:
        await session.goto(portal + "/typing.html")
        home = session.page.url
        await remote_input.apply(session, remote_input.parse({"kind": "duplicate_tab"}))
        assert len(session.tabs()) == 2 and session.page.url == home
        await remote_input.apply(session, remote_input.parse({"kind": "navigate", "url": portal + "/feed.html"}))
        assert session.page.url.endswith("/feed.html")
        await remote_input.apply(session, remote_input.parse({"kind": "back"}))
        assert session.page.url == home
        await remote_input.apply(session, remote_input.parse({"kind": "switch_tab", "index": 0}))
        await remote_input.apply(session, remote_input.parse({"kind": "close_tab", "index": 1}))
        assert len(session.tabs()) == 1
        with pytest.raises(ActionError):  # the site policy still applies to a person's address bar
            await remote_input.apply(session, remote_input.parse({"kind": "navigate", "url": "http://169.254.169.254/"}))
        with pytest.raises(ValidationError):
            remote_input.parse({"kind": "navigate", "url": ""})


async def test_tab_changes_are_announced(portal):
    seen: list[dict] = []
    async with open_session(portal + "/typing.html") as session:
        watcher = TabWatcher(session, seen.append)
        watcher.start()
        await asyncio.sleep(0.8)
        await session.open_tab(portal + "/feed.html")
        await asyncio.sleep(1.2)
        await watcher.stop()
    assert [len(e["tabs"]) for e in seen][0] == 1 and len(seen[-1]["tabs"]) == 2
    assert [t["active"] for t in seen[-1]["tabs"]] == [False, True]


def test_the_richer_inputs_are_validated():
    ok = remote_input.parse
    assert ok({"kind": "click", "x": 0.5, "y": 0.5, "button": "right", "clicks": 2}).clicks == 2
    assert ok({"kind": "move", "x": 0, "y": 1}).kind == "move"
    assert ok({"kind": "key", "key": "a", "mods": ["Control"]}).key == "a"  # select all
    assert ok({"kind": "type", "text": "x" * 1500}).kind == "type"  # a paste
    for bad in ({"kind": "key", "key": "a"},  # a letter alone is typing, not a key
                {"kind": "key", "key": "w", "mods": ["Control"]},  # close tab, not an editing shortcut
                {"kind": "key", "key": "F5"}, {"kind": "click", "x": 0.5, "y": 0.5, "clicks": 9}, {"kind": "type", "text": "x" * 2001},
                {"kind": "click", "x": 0.5, "y": 0.5, "button": "back"}):
        with pytest.raises(ValidationError):
            ok(bad)
