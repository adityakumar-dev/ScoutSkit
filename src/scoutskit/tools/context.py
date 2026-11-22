"""What every tool group needs, passed once instead of threaded through each function."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path

from ..browser import BrowserSession
from .collector import Collector


@dataclass
class ToolContext:
    session: BrowserSession
    collector: Collector
    verdict: Callable[[], str | None] | None = None  # why `done` is premature, or None when it is fine
    workdir: Path | None = None  # where scripts and their output are kept; None disables code execution
    search: Callable[[str], Awaitable[list]] | None = None  # web search (real results as data); None: this run has none
    evidence_refusals: int = 0  # how often `done` was refused because the page shows the list is incomplete
