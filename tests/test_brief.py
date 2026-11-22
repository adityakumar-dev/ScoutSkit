"""The brief: search for context, let the model pick sources by number only, and wait for the person's approval."""

import asyncio

import pytest

from scoutskit import brief as brief_module
from scoutskit.brief import research
from scoutskit.control import Decision, PlanGate
from scoutskit.provider.llm import LLMError, LLMResult
from scoutskit.search import Hit, gather, same_page


class FakeSource:
    def __init__(self, name, hits=None, error=None):
        self.name, self.hits, self.error, self.queries = name, hits or [], error, []

    async def search(self, query, limit):
        self.queries.append(query)
        if self.error:
            raise self.error
        return self.hits


OFFICIAL = Hit("Syllabus | University", "https://uni.example/syllabus", "official syllabus page", "duckduckgo")
COPY = Hit("Syllabus copy", "https://www.copies.example/doc/1", "a copy", "duckduckgo")


def model(replies):
    """A stand-in for complete_json that answers in turn and remembers what it was asked."""
    asked = []

    async def complete(provider, system, user):
        asked.append((system, user))
        return LLMResult(replies[len(asked) - 1], 10, 5, 1)

    return complete, asked


async def test_sources_are_merged_and_a_failing_source_only_leaves_a_note():
    good = FakeSource("good", [OFFICIAL, Hit("Same page again", "http://www.uni.example/syllabus/", "", "good"), COPY])
    bad = FakeSource("bad", error=RuntimeError("rate limited"))
    hits, notes = await gather([good, bad], ["q1", "q2"])
    assert [h.url for h in hits] == [OFFICIAL.url, COPY.url]  # the same page twice counts once
    assert len(notes) == 2 and "bad gave nothing for 'q1' (RuntimeError: rate limited)" in notes
    assert same_page("http://www.A.example/x/#top") == same_page("https://a.example/x")


async def test_the_model_picks_by_number_and_cannot_invent_a_url(monkeypatch):
    complete, asked = model([
        {"queries": ["university official site", "btech syllabus"]},
        {"understanding": "wants the syllabus", "picks": [{"n": 2, "why": "official"}, {"n": 99, "why": "made up"}, {"n": "https://evil.example", "why": "x"}],
         "start": 2, "goal": "get the syllabus", "item_name": "syllabus", "min_items": 1, "steps": ["open the site", "find the syllabus"]},
    ])
    monkeypatch.setattr(brief_module, "complete_json", complete)
    source = FakeSource("ddg", [COPY, OFFICIAL])
    result = await research(None, "download the btech syllabus", None, [source])
    assert source.queries == ["university official site", "btech syllabus"]
    assert result.plan.start_url == OFFICIAL.url and [h.url for h, _ in result.picks] == [OFFICIAL.url]
    assert "1. [duckduckgo] Syllabus copy" in asked[1][1] and "never write a URL" in asked[1][0]
    event = result.to_event()
    assert event["picks"][0]["why"] == "official" and event["steps"] == ["open the site", "find the syllabus"]


async def test_a_named_site_skips_the_search_and_added_context_brings_its_own_sources(monkeypatch):
    complete, asked = model([{"understanding": "u", "picks": [{"n": 1, "why": "yours"}], "start": 1, "steps": []}])
    monkeypatch.setattr(brief_module, "complete_json", complete)
    source = FakeSource("ddg", [OFFICIAL])
    result = await research(None, "get items", "https://shop.example/list", [source], context="also see https://other.example/page")
    assert source.queries == [] and result.plan.start_url == "https://shop.example/list"
    assert [h.url for h in result.sources] == ["https://shop.example/list", "https://other.example/page"]
    assert "USER CONTEXT: also see https://other.example/page" in asked[0][1]


async def test_nothing_found_is_an_error_that_says_what_to_do(monkeypatch):
    complete, _ = model([{"queries": ["x"]}])
    monkeypatch.setattr(brief_module, "complete_json", complete)
    with pytest.raises(LLMError, match="give a start URL or add context"):
        await research(None, "find something", None, [FakeSource("ddg", error=RuntimeError("down"))])


async def test_the_plan_waits_for_an_answer_and_an_answer_counts_once():
    states = []
    gate = PlanGate(announce=lambda state, topic: states.append(state))
    assert gate.answer(Decision(True)) is False  # nothing is waiting yet
    waiting = asyncio.create_task(gate.ask())
    await asyncio.sleep(0)
    assert gate.waiting
    assert gate.answer(Decision(False, "the site is uni.example")) is True
    assert (await waiting) == Decision(False, "the site is uni.example")
    assert gate.answer(Decision(True)) is False and states == ["waiting", "revising"]


async def test_a_re_plan_keeps_the_earlier_sources(monkeypatch):
    complete, asked = model([{"queries": ["new query"]}, {"understanding": "u", "picks": [{"n": 2, "why": "kept"}], "start": 2, "steps": []}])
    monkeypatch.setattr(brief_module, "complete_json", complete)
    result = await research(None, "get the syllabus", None, [FakeSource("ddg", [COPY])], context="only CSE", earlier=[OFFICIAL, COPY])
    assert [h.url for h in result.sources] == [OFFICIAL.url, COPY.url]  # nothing lost, nothing twice
    assert result.plan.start_url == COPY.url
