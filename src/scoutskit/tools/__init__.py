"""The bounded tool set the agent may call, grouped by what the tools do.

build_registry() assembles every group into one ToolRegistry, so the prompt, the typed
LangChain tools and the dispatcher all come from a single description of each tool.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from ..browser import BrowserSession
from . import actions, control, extraction, reading, web
from .collector import Collector
from .context import ToolContext
from .registry import Tool, ToolRegistry, langchain_tools

__all__ = ["Collector", "Tool", "ToolContext", "ToolRegistry", "build_registry", "langchain_tools"]


def build_registry(
    session: BrowserSession, collector: Collector, verdict: Callable[[], str | None] | None = None, workdir: Path | None = None,
    search: Callable | None = None,
) -> ToolRegistry:
    ctx = ToolContext(session, collector, verdict, workdir, search)
    registry = ToolRegistry(scrub=session.scrub)
    for group in (actions, reading, extraction, control, web):
        group.register(registry, ctx)
    return registry
