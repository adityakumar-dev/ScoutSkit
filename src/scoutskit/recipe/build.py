"""Turn a finished run's evidence (actions.jsonl, result.json) into a Recipe."""

from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import urlparse

from .model import Feed, Recipe, Step

REPLAYABLE = {"goto", "click", "fill", "select", "press", "scroll", "hover", "wait_for", "back", "switch_tab", "close_tab", "open_tab"}
READS_THE_PAGE = ("HTML_PATH", "RENDERED_PATH")  # a script that mentions neither only holds data typed in by the model


def from_run(run_dir: Path, feed: Feed | None = None, agent: str | None = None) -> Recipe | None:
    """None when the run has no start event. Steps that failed, or that read without changing anything, are left out.
    `agent`: in a run with sub-agents, only that sub-agent's steps (the one whose result was accepted).

    A script that reads the page is the extraction; failing that, the data request the rows came from (see source.py)."""
    entries = [json.loads(line) for line in (run_dir / "actions.jsonl").read_text(encoding="utf-8").splitlines()]
    if agent is not None:
        entries = [e for e in entries if e.get("agent") == agent]
    start = next((e for e in entries if e.get("event") == "start"), None)
    if start is None:
        return None
    steps = [_step(e) for e in entries if e.get("tool") in REPLAYABLE and e.get("ok")]
    steps = [s for s in steps if s is not None]
    script = _extraction_script(entries)
    if script is not None:
        path = urlparse(entries[-1].get("url_to") or start["plan"]["start_url"]).path
        steps += [Step("run_python", {"code": script}, path), Step("use_script_output", {}, path)]
    plan = start["plan"]
    return Recipe(task=start["task"], start_url=plan["start_url"], steps=steps, fields=list(plan.get("fields", [])),
                  key_field=plan.get("key_field", ""), expected_items=_items(run_dir),
                  feed=None if script is not None else feed, web=bool(start.get("web")), extracts=script is not None or feed is not None)


def _step(entry: dict) -> Step | None:
    args = dict(entry["args"])
    path = urlparse(entry.get("url_from", "")).path
    if "ref" not in args:
        return Step(entry["tool"], args, path)
    if not entry.get("label"):
        return None  # an element we cannot name again cannot be found again
    del args["ref"]
    return Step(entry["tool"], args, path, target=entry["label"], nth=entry.get("nth", 0))


def _extraction_script(entries: list[dict]) -> str | None:
    """The code behind the final data, when it reads the page: the last good run_python before the last good use_script_output."""
    loaded = [i for i, e in enumerate(entries) if e.get("tool") == "use_script_output" and e.get("ok")]
    if not loaded:
        return None
    for entry in reversed(entries[: loaded[-1]]):
        if entry.get("tool") == "run_python" and entry.get("ok"):
            code = str(entry["args"].get("code", ""))
            return code if any(name in code for name in READS_THE_PAGE) else None
    return None


def _items(run_dir: Path) -> int:
    try:
        return int(json.loads((run_dir / "result.json").read_text(encoding="utf-8"))["summary"]["items"])
    except (OSError, ValueError, KeyError):
        return 0
