"""A CAPTCHA is a check for a person: the agent hands over the browser and waits, once per site; a person's "skip" ends it."""

import asyncio
import json

from scoutskit.agent import Agent
from scoutskit.browser import open_session
from scoutskit.control import RunControl
from scoutskit.recorder import RunRecorder
from test_agent_loop import ScriptedChat, plan


def log(recorder):
    return [json.loads(line) for line in (recorder.dir / "actions.jsonl").read_text().splitlines()]


async def run_with_a_person(portal, tmp_path, brain, person):
    """Runs the agent; `person(session, control)` plays the human once the agent has asked for the browser."""
    control, recorder = RunControl(), RunRecorder(tmp_path)
    async with open_session(portal + "/captcha.html") as session:
        agent = Agent(session, [ScriptedChat(brain=brain)], ["scripted"], recorder, max_steps=4, control=control)
        working = asyncio.create_task(agent.run("get the page", plan(start_url=portal + "/captcha.html", min_items=1)))
        while not control.user_driving:
            await asyncio.sleep(0.05)
            assert not working.done(), "the agent never asked for help"
        await person(session, control)
        await working
    return log(recorder)


def goes_to(portal, *pages, seen=None):
    """A model that opens the pages in turn; `seen` collects every prompt it was shown."""
    visits = iter(pages)

    async def brain(page: str) -> dict:
        if seen is not None:
            seen.append(page)
        return {"tool": "goto", "args": {"url": f"{portal}/{next(visits, pages[-1])}"}}
    return brain


async def test_the_person_is_asked_before_the_model_sees_the_page_and_the_agent_carries_on_afterwards(portal, tmp_path):
    """The start page is a CAPTCHA. A model that saw "I'm not a robot" might tick it itself, so the request comes first."""
    async def person(session, control):
        await session.goto(portal + "/feed.html")  # what the person did in the browser
        control.release()

    prompts = []
    entries = await run_with_a_person(portal, tmp_path, goes_to(portal, "feed.html", seen=prompts), person)
    names = [e.get("event") for e in entries]
    assert names.index("help_needed") < names.index("help_done")
    needed = next(e for e in entries if e.get("event") == "help_needed")
    assert needed["kind"] == "captcha" and needed["host"] == "127.0.0.1" and needed["url"].endswith("/captcha.html")
    assert next(e for e in entries if e.get("event") == "help_done")["skipped"] is False
    assert "a person handled it" in prompts[0] and "I'm not a robot" not in prompts[0]  # told once, and shown the page as it is now
    assert not any(e.get("event") == "finding" for e in entries)  # nothing was blocked for good


async def test_skipping_is_a_finding_and_the_site_is_not_asked_about_again(portal, tmp_path):
    async def person(session, control):
        control.release("skip")

    prompts = []
    entries = await run_with_a_person(portal, tmp_path, goes_to(portal, "captcha.html", "captcha.html", "captcha.html", seen=prompts), person)
    assert [e["event"] for e in entries if e.get("event") in ("help_needed", "help_done")] == ["help_needed", "help_done"]  # asked once
    assert next(e for e in entries if e.get("event") == "help_done")["skipped"] is True
    findings = [e for e in entries if e.get("event") == "finding"]
    assert any("chose to skip" in f["detail"] for f in findings)
    assert any("showed a block page" in f["detail"] for f in findings)  # the second time it is just a block
    assert "chose to skip" in prompts[0] and "do not go back" in prompts[0]


async def test_without_a_person_to_ask_a_captcha_is_a_block_as_before(portal, tmp_path):
    recorder = RunRecorder(tmp_path)
    async with open_session(portal + "/captcha.html") as session:
        agent = Agent(session, [ScriptedChat(brain=goes_to(portal, "captcha.html"))], ["scripted"], recorder, max_steps=2)  # no control: the command line
        await agent.run("get the page", plan(start_url=portal + "/captcha.html", min_items=1))
    entries = log(recorder)
    assert not any(e.get("event") == "help_needed" for e in entries)
    assert any(e.get("event") == "finding" and e["kind"] == "access_denied" for e in entries)


async def test_a_hidden_captcha_frame_on_an_ordinary_page_asks_nobody(portal, tmp_path):
    """Sites load an invisible reCAPTCHA in a background frame; the person sees an ordinary page, so there is nothing to solve."""
    control, recorder = RunControl(), RunRecorder(tmp_path)
    async with open_session(portal + "/reviews_page.html") as session:
        agent = Agent(session, [ScriptedChat(brain=goes_to(portal, "feed.html"))], ["scripted"], recorder, max_steps=2, control=control)
        await agent.run("get the page", plan(start_url=portal + "/reviews_page.html", min_items=1))
    entries = log(recorder)
    assert not any(e.get("event") in ("help_needed", "finding") for e in entries)
    assert not control.user_driving


async def test_a_page_that_announces_itself_as_a_human_check_in_its_title_asks_a_person(portal, tmp_path):
    async def person(session, control):
        control.release()

    prompts = []
    control, recorder = RunControl(), RunRecorder(tmp_path)
    async with open_session(portal + "/moment.html") as session:
        agent = Agent(session, [ScriptedChat(brain=goes_to(portal, "feed.html", seen=prompts))], ["scripted"], recorder, max_steps=2, control=control)
        working = asyncio.create_task(agent.run("get the page", plan(start_url=portal + "/moment.html", min_items=1)))
        while not control.user_driving:
            await asyncio.sleep(0.05)
            assert not working.done()
        await person(session, control)
        await working
    needed = next(e for e in log(recorder) if e.get("event") == "help_needed")
    assert needed["host"] == "127.0.0.1" and needed["url"].endswith("/moment.html")
