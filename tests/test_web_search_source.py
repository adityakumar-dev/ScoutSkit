"""The free web search source retries a flaky ddgs call, and says plainly when it still finds nothing."""

import sys
import types

import pytest

from scoutskit.search import WebSearch, make_sources
from scoutskit.search import duckduckgo as module


def fake_ddgs(monkeypatch, outcomes):
    """A stand-in `ddgs` module whose text() returns or raises the given outcomes in turn."""
    calls = []

    class FakeDDGS:
        def text(self, query, max_results=5):
            calls.append(query)
            outcome = outcomes[min(len(calls) - 1, len(outcomes) - 1)]
            if isinstance(outcome, Exception):
                raise outcome
            return outcome

    monkeypatch.setitem(sys.modules, "ddgs", types.SimpleNamespace(DDGS=FakeDDGS))
    monkeypatch.setattr(module, "RETRY_WAIT_S", 0)
    return calls


async def test_a_failed_attempt_is_retried_and_the_results_are_labelled_web(monkeypatch):
    rows = [{"title": "Syllabus", "href": "https://uni.example/s.pdf", "body": "the syllabus"}]
    calls = fake_ddgs(monkeypatch, [RuntimeError("No results found."), RuntimeError("No results found."), rows])
    hits = await WebSearch().search("uni syllabus", 5)
    assert len(calls) == 3 and [(h.url, h.source) for h in hits] == [("https://uni.example/s.pdf", "web")]


async def test_when_every_attempt_fails_the_error_is_raised_so_the_brief_can_note_it(monkeypatch):
    calls = fake_ddgs(monkeypatch, [RuntimeError("No results found.")])
    with pytest.raises(RuntimeError, match="No results"):
        await WebSearch().search("x", 5)
    assert len(calls) == module.RETRIES


def test_the_old_source_name_still_works():
    assert type(make_sources(["duckduckgo"])[0]) is WebSearch and type(make_sources(["web"])[0]) is WebSearch
