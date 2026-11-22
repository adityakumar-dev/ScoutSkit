"""Tools that end the run: done and fail."""

from __future__ import annotations

from ..browser import ActionError
from .context import ToolContext
from .registry import Tool, ToolRegistry


def register(registry: ToolRegistry, ctx: ToolContext) -> None:
    async def _evidence_of_missing_items() -> str | None:
        """What the page itself shows about missing items: a total it states, or more rows in its source than on screen."""
        collected = len(ctx.collector.rows)
        if not collected and ctx.session.files and ctx.session.files.saved:
            return None  # the files are the result: a table on the page that was not collected is not what was asked for
        stated = await ctx.session.stated_total()
        if stated and collected < stated:
            return f"the page states {stated} entries and you have collected {collected}"
        census = await ctx.session.census(list(ctx.collector.rows))
        if census and collected < census.raw_rows:
            return f"{census.sentence()}, and you have collected {collected}"
        return None

    async def done(reason: str | None = None) -> str:
        """Finish. The plan's expected count is only a guess, so a stated reason can override it. Evidence from the page itself
        is stricter: the first `done` is always refused with that evidence; a reason is accepted only afterwards, with a loud warning
        (the task may genuinely ask for a subset)."""
        evidence = await _evidence_of_missing_items()
        if evidence and (not reason or ctx.evidence_refusals == 0):
            ctx.evidence_refusals += 1
            raise ActionError(
                f"done rejected: {evidence}. Collect the rest first: the raw HTML source usually holds every row (grep_source, then run_python "
                "on HTML_PATH). Only if the task asks for a subset, call done again with a `reason` that says which."
            )
        problem = ctx.verdict() if ctx.verdict else None
        if evidence:
            return f"task complete with a WARNING: {evidence}. Reason given: {reason}"
        if problem and not reason:
            raise ActionError(
                f"done rejected: {problem}. Keep exploring; if there really are no more items, call done again with a `reason` "
                "that says why (for example what the page shows)."
            )
        if problem:
            return f"task complete with a warning: {problem}. Reason given: {reason}"
        return "task complete"

    async def fail(reason: str) -> str:
        return f"gave up: {reason}"

    registry.register(Tool(
        "done", "Finish: every requested item has been collected. If fewer items than expected were found, the first call is refused; "
        "call again with a reason (what the page shows) to finish anyway.",
        {"reason": "why you are done although fewer items than expected were found?"}, done,
    ))
    registry.register(Tool("fail", "Give up: the task is impossible.", {"reason": "why it is impossible"}, fail))
