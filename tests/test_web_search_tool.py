"""Search as a tool: results as data, never a search engine page in the browser; documents found by search are kept directly."""

import pytest

from scoutskit import team as team_module
from scoutskit.brief import Brief
from scoutskit.browser import ActionError, FileStore, open_browser, open_session
from scoutskit.provider.llm import LLMResult
from scoutskit.recorder import RunRecorder
from scoutskit.search import Hit, is_search_page
from scoutskit.team import Team
from scoutskit.tools import Collector, build_registry
from test_agent_loop import ScriptedChat, plan
from test_team import events


def test_search_engine_result_pages_are_recognised_and_ordinary_pages_are_not():
    for url in ("https://duckduckgo.com/?q=cyber+security", "https://www.google.com/search?q=x", "https://www.google.co.in/search?q=x",
                "https://www.bing.com/search?q=x", "https://search.brave.com/search?q=x", "https://html.duckduckgo.com/html?q=x"):
        assert is_search_page(url), url
    for url in ("https://uktech.ac.in/en/page/syllabus", "https://duckduckgo.com/about", "https://example.com/search?q=x", "https://notgoogle.example/search?q=x",
                "https://www.google.com/maps/place/x"):
        assert not is_search_page(url), url


async def test_the_agent_gets_web_search_and_cannot_open_a_search_page(portal):
    asked = []

    async def search(query):
        asked.append(query)
        return [Hit("Syllabus", "https://uni.example/s.pdf", "the pdf", "duckduckgo")]

    async with open_session(portal + "/index.html") as session:
        await session.goto(portal + "/index.html")
        registry = build_registry(session, Collector([]), search=search)
        assert "web_search" in registry.names()
        out, is_read = await registry.call("web_search", {"query": "uni syllabus"})
        assert is_read
        assert "1. [duckduckgo] Syllabus" in out and "https://uni.example/s.pdf" in out and "save_file" in out
        for tool in ("goto", "open_tab"):
            with pytest.raises(ActionError, match="call web_search"):
                await registry.call(tool, {"url": "https://duckduckgo.com/?q=uni+syllabus"})
        plain = build_registry(session, Collector([]))
        assert "web_search" not in plain.names()  # a run without search has no such tool
    assert asked == ["uni syllabus"]


async def test_files_are_the_result_so_a_table_that_was_not_collected_does_not_block_done(portal, tmp_path):
    store = FileStore(tmp_path / "files")
    async with open_session(portal + "/records.html", files=store) as session:
        await session.goto(portal + "/records.html")
        registry = build_registry(session, Collector([]))
        with pytest.raises(ActionError, match="done rejected"):
            await registry.call("done", {})  # a table with many rows, nothing collected, nothing saved
        await session.save_file(portal + "/report.pdf")
        assert (await registry.call("done", {}))[0] == "task complete"


async def test_a_search_result_that_is_the_document_is_saved_at_once(portal, tmp_path, monkeypatch):
    async def verified(provider, system, user):
        assert "report.pdf" in user
        return LLMResult({"complete": True, "why": "the document"}, 1, 1, 1)

    monkeypatch.setattr(team_module, "complete_json", verified)
    pick = Hit("Annual report", portal + "/report.pdf", "", "duckduckgo")
    brief = Brief(task="get the report", understanding="u", plan=plan(start_url=pick.url, min_items=1, item_name="report"),
                  sources=[pick], picks=[(pick, "the document itself")], steps=[], agents=1)
    prompts = []

    async def brain(page: str) -> dict:
        prompts.append(page)
        return {"tool": "done", "args": {}}

    recorder = RunRecorder(tmp_path)
    async with open_browser() as host:
        team = Team(host, brief, "get the report", providers=[type("P", (), {"name": "scripted"})()], make_models=lambda: [ScriptedChat(brain=brain)],
                    recorder=recorder, max_steps=4, web=False)
        result = await team.run()
    assert result.winner is not None and (recorder.files_dir / "report.pdf").exists()
    assert "FILES SAVED FOR THE USER: report.pdf (if they already answer the task, call done now)" in prompts[0]  # the agent is told what it already has
    direct = next(e for e in events(recorder) if e.get("event") == "direct_file")
    assert direct["name"] == "report.pdf" and "error" not in direct
