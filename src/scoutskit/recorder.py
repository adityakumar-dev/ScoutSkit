"""Per-run evidence: every action is appended to actions.jsonl as it happens."""

from __future__ import annotations

import csv
import json
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any


class RunRecorder:
    def __init__(self, base_dir: Path) -> None:
        stamp = time.strftime("%Y%m%d-%H%M%S")
        self.dir, taken = base_dir / stamp, 1
        while True:  # runs that start in the same second (parallel runs) must not share a folder
            try:
                (self.dir / "screenshots").mkdir(parents=True)
                break
            except FileExistsError:
                taken += 1
                self.dir = base_dir / f"{stamp}-{taken}"
        self._actions = self.dir / "actions.jsonl"
        self._started = time.time()
        self.listeners: list[Callable[[dict], None]] = []  # told about every entry as it is logged (the server's live stream)

    @property
    def run_id(self) -> str:
        return self.dir.name

    @property
    def code_dir(self) -> Path:
        return self.dir / "code"

    @property
    def files_dir(self) -> Path:
        return self.dir / "files"

    def for_agent(self, agent: str) -> "AgentRecorder":
        return AgentRecorder(self, agent)

    def log(self, **entry: Any) -> None:
        entry["t"] = round(time.time() - self._started, 2)
        with self._actions.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry, ensure_ascii=False, default=str) + "\n")
        for listener in self.listeners:
            listener(entry)

    async def screenshot(self, session, name: str) -> str:
        relative = f"screenshots/{name}.png"
        try:
            await session.screenshot(self.dir / relative)
        except Exception as error:  # evidence is best effort; never fail the run for it
            self.log(event="screenshot_failed", name=name, error=type(error).__name__)
            return ""
        return relative

    def save_result(self, rows: list[dict[str, str]], fields: list[str], summary: dict[str, Any]) -> None:
        (self.dir / "result.json").write_text(
            json.dumps({"summary": summary, "rows": rows}, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        with (self.dir / "result.csv").open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(rows)


class AgentRecorder:
    """One sub-agent's view of the run's recorder: its entries carry its id, and its screenshots and scripts get their own names."""

    def __init__(self, run: RunRecorder, agent: str) -> None:
        self.run, self.agent = run, agent

    @property
    def dir(self) -> Path:
        return self.run.dir

    @property
    def code_dir(self) -> Path:
        return self.run.code_dir / self.agent

    def log(self, **entry: Any) -> None:
        self.run.log(agent=self.agent, **entry)

    async def screenshot(self, session, name: str) -> str:
        return await self.run.screenshot(session, f"{self.agent}-{name}")
