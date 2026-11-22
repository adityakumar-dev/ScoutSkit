"""Repeat a recipe with no model, and say exactly where the site no longer matches it.

Nothing is guessed: when the page or an element is not what was recorded, replay reports a finding
(the evidence that something changed) instead of looking for a "similar" element.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlparse

from ..browser import ActionError, BrowserSession
from ..browser.feeds import records_in
from ..tools import Collector, build_registry
from .model import Recipe, Step


@dataclass(frozen=True)
class Finding:
    kind: str  # page_changed | target_missing | step_failed | feed_missing | result_changed | no_extraction
    step: int  # 1-based; 0 for the run as a whole
    detail: str
    blocking: bool = False


@dataclass
class ReplayReport:
    steps_done: int = 0
    findings: list[Finding] = field(default_factory=list)
    rows: list[dict[str, str]] = field(default_factory=list)
    fields: list[str] = field(default_factory=list)
    files: list[str] = field(default_factory=list)  # names of the files this replay saved

    @property
    def status(self) -> str:
        if any(f.blocking for f in self.findings):
            return "diverged"
        return "changed" if self.findings else "replayed"


def find_target(labels: dict[str, str], step: Step) -> str | None:
    """The ref of the element the step was recorded on, matched by role and name."""
    matches = [ref for ref, label in labels.items() if label == step.target]
    return matches[step.nth] if len(matches) > step.nth else None


async def replay(session: BrowserSession, recipe: Recipe, workdir: Path, start_url: str | None = None, log=None) -> ReplayReport:
    report = ReplayReport()
    collector = Collector(list(recipe.fields), recipe.key_field)
    registry = build_registry(session, collector, workdir=workdir)
    try:
        await session.goto(start_url or recipe.start_url)
    except ActionError as error:
        report.findings.append(Finding("step_failed", 0, f"could not open the start page: {error}", blocking=True))
        return report
    for number, step in enumerate(recipe.steps, 1):
        _, labels = await session.snapshot()
        path = urlparse(session.page.url).path
        if path != step.url_path:
            report.findings.append(Finding("page_changed", number, f"recorded on {step.url_path or '/'} but the browser is on {path or '/'}"))
        args = dict(step.args)
        if step.target:
            ref = find_target(labels, step)
            if ref is None:
                report.findings.append(Finding("target_missing", number, f"no element {step.target} (number {step.nth + 1}) on {path or '/'}", blocking=True))
                break
            args["ref"] = ref
        try:
            text, _ = await registry.call(step.tool, args)
        except ActionError as error:
            report.findings.append(Finding("step_failed", number, f"{step.tool} failed: {error}", blocking=True))
            break
        report.steps_done = number
        if log:
            log(step=number, tool=step.tool, target=step.target, ok=True, outcome=text[:300])
    if recipe.feed and not any(f.blocking for f in report.findings):
        await _read_feed(session, recipe, collector, report)
    report.rows, report.fields = list(collector.rows.values()), collector.fields
    report.files = [f.name for f in session.files.saved] if session.files else []
    _compare_result(report, recipe)
    return report


async def _read_feed(session: BrowserSession, recipe: Recipe, collector: Collector, report: ReplayReport) -> None:
    """Take the items from the same data request the recorded run used."""
    feed = recipe.feed
    for entry in reversed(session.network_log(re.escape(feed.path), limit=500)):
        records = records_in(await session.network_body(entry.index, max_chars=10_000_000)) if entry.status == 200 else None
        if records:
            collector.fields = []
            collector.ensure_fields(dict.fromkeys(feed.fields))  # adopts the columns and picks the key field
            collector.add([{f: record.get(f) for f in feed.fields} for record in records])
            return
    report.findings.append(Finding("feed_missing", 0, f"the page made no data request to {feed.path} this time", blocking=True))


def _compare_result(report: ReplayReport, recipe: Recipe) -> None:
    if any(f.blocking for f in report.findings):
        return
    if recipe.expected_files and len(report.files) != len(recipe.expected_files):
        report.findings.append(Finding("result_changed", 0, f"the recorded run saved {len(recipe.expected_files)} files, this replay {len(report.files)}"))
    if not recipe.extracts and not recipe.expected_files:
        report.findings.append(Finding("no_extraction", 0, "the recorded run did not get its data with a script that reads the page, so replay repeats the actions only"))
    elif recipe.extracts and len(report.rows) != recipe.expected_items:
        report.findings.append(Finding("result_changed", 0, f"the recorded run collected {recipe.expected_items} items, this replay {len(report.rows)}"))
