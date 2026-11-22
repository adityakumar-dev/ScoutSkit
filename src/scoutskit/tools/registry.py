"""Tool and ToolRegistry: every tool is described once (name, parameters, handler).

The same description feeds the model's prompt and builds the typed LangChain tools,
so the prompt can never promise a tool that does not exist.
"""

from __future__ import annotations

import inspect
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from langchain_core.tools import StructuredTool
from pydantic import ConfigDict, Field, create_model

from ..browser import ActionError

MAX_OUTPUT_CHARS = 6_000


@dataclass(frozen=True)
class Tool:
    name: str
    description: str
    params: dict[str, str]  # parameter name -> short description; a trailing '?' marks it optional
    handler: Callable[..., Awaitable[str]]
    reads: bool = False  # True: the returned text is information for the model, not just an acknowledgement


class ToolRegistry:
    def __init__(self, scrub: Callable[[str], Awaitable[str]] | None = None) -> None:
        self._tools: dict[str, Tool] = {}
        self._scrub = scrub  # applied to every output, so nothing that must stay hidden reaches the model or the log

    def register(self, tool: Tool) -> None:
        self._tools[tool.name] = tool

    def __contains__(self, name: str) -> bool:
        return name in self._tools

    def get(self, name: str) -> Tool:
        return self._tools[name]

    def names(self) -> list[str]:
        return list(self._tools)

    def tools(self) -> list[Tool]:
        return list(self._tools.values())

    def describe(self) -> str:
        lines = []
        for tool in self._tools.values():
            args = ", ".join(f"{p}{'?' if d.endswith('?') else ''}" for p, d in tool.params.items())
            detail = "; ".join(f"{p}: {d.rstrip('?')}" for p, d in tool.params.items())
            lines.append(f"- {tool.name}({args}): {tool.description}" + (f" [{detail}]" if detail else ""))
        return "\n".join(lines)

    async def call(self, name: str, args: dict[str, Any]) -> tuple[str, bool]:
        """Run a tool. Returns (outcome text, whether the text is a read result for the model)."""
        tool = self._tools[name]
        accepted = set(inspect.signature(tool.handler).parameters)
        unknown = set(args) - accepted
        if unknown:
            raise ActionError(f"{name} does not take {sorted(unknown)}; it takes {sorted(accepted)}")
        missing = [p for p, d in tool.params.items() if not d.endswith("?") and args.get(p) in (None, "")]
        if missing:
            raise ActionError(f"{name} needs {missing}")
        output = await tool.handler(**args)
        if self._scrub:
            output = await self._scrub(output)
        if len(output) > MAX_OUTPUT_CHARS:
            output = output[:MAX_OUTPUT_CHARS] + f"\n[output cut at {MAX_OUTPUT_CHARS:,} characters, {len(output) - MAX_OUTPUT_CHARS:,} more not shown: narrow it with a ref, find, or use code]"
        return output, tool.reads


def langchain_tools(registry: ToolRegistry) -> list[StructuredTool]:
    """Typed LangChain tools from the registry; argument types come from each handler's signature."""
    result = []
    for tool in registry.tools():
        fields = {}
        for name, param in inspect.signature(tool.handler, eval_str=True).parameters.items():
            annotation = Any if param.annotation is inspect.Parameter.empty else param.annotation
            default = ... if param.default is inspect.Parameter.empty else param.default
            fields[name] = (annotation, Field(default, description=tool.params.get(name, "").rstrip("?")))

        async def run(_name: str = tool.name, **kwargs: Any) -> str:
            text, _ = await registry.call(_name, kwargs)
            return text

        schema = create_model(f"{tool.name}_args", __config__=ConfigDict(extra="forbid"), **fields)  # unknown args are errors
        result.append(StructuredTool.from_function(coroutine=run, name=tool.name, description=tool.description, args_schema=schema))
    return result
