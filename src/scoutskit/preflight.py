"""Is everything ready? One command before a demo: browser, sandbox, model, search, interface, disk.

Each check says what it found in a few words and, when it fails, what to do. Nothing here changes anything.
"""

from __future__ import annotations

import asyncio
import tempfile
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path

UI_DIST = Path(__file__).resolve().parents[2] / "ui" / "dist"


@dataclass(frozen=True)
class Check:
    name: str
    ok: bool
    detail: str
    fix: str = ""


async def browser() -> Check:
    try:
        from .browser import open_session

        started = time.perf_counter()
        async with open_session("https://example.com", scope="web") as session:
            await session.page.set_content("<title>ok</title><p>ready</p>")
            title = await session.title()
        return Check("Browser", title == "ok", f"Chromium starts ({time.perf_counter() - started:.1f}s)", "run: uv run playwright install chromium")
    except Exception as error:
        return Check("Browser", False, f"{type(error).__name__}: {str(error)[:80]}", "run: uv run playwright install chromium")


async def sandbox() -> Check:
    from . import sandbox as box

    reason = box.unavailable_reason()
    return Check("Code sandbox", not reason, "bubblewrap works" if not reason else reason, "install bubblewrap (bwrap); without it the agent cannot run extraction scripts")


async def model() -> Check:
    try:
        from .provider import ensure_providers, load_settings

        settings = load_settings()
        names, note = await ensure_providers(settings)
        if not names:
            return Check("Model", False, "no provider works", "run: uv run scoutskit providers --check, and put a key in .env")
        first = names[0]
        detail = f"{first} ({settings.providers[first].model})" + (f"; {note}" if note else "")
        return Check("Model", first == settings.default_provider, detail, f"the default provider is {settings.default_provider!r}: check its key in .env" if first != settings.default_provider else "")
    except Exception as error:
        return Check("Model", False, f"{type(error).__name__}: {str(error)[:80]}", "check scoutskit.toml and .env")


async def search() -> Check:
    try:
        from .search import gather, make_sources

        hits, notes = await gather(make_sources(["web", "wikipedia"]), ["Uttarakhand Technical University"], per_query=3)
        return Check("Web search", bool(hits), f"{len(hits)} results" + (f" ({len(notes)} source(s) failed)" if notes else ""), "no internet, or the search engines are refusing this machine right now: retry in a minute")
    except Exception as error:
        return Check("Web search", False, f"{type(error).__name__}: {str(error)[:80]}", "check the internet connection")


async def interface() -> Check:
    built = (UI_DIST / "index.html").is_file()
    return Check("Interface", built, "built (ui/dist)" if built else "not built", "run: cd ui && npm install && npm run build")


async def storage() -> Check:
    try:
        from .provider import load_settings

        folder = load_settings().runs_dir
        folder.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=folder):
            pass
        return Check("Runs folder", True, f"writable ({folder})")
    except Exception as error:
        return Check("Runs folder", False, f"{type(error).__name__}: {str(error)[:80]}", "check [runs] dir in scoutskit.toml")


CHECKS: list[Callable[[], Awaitable[Check]]] = [interface, storage, sandbox, browser, model, search]


async def _safely(check: Callable[[], Awaitable[Check]]) -> Check:
    try:
        return await check()
    except Exception as error:  # a check that crashes is a failed check, not a crashed pre-flight
        return Check(getattr(check, "__name__", "check").capitalize(), False, f"crashed: {type(error).__name__}: {str(error)[:80]}")


async def run_all() -> list[Check]:
    return list(await asyncio.gather(*(_safely(check) for check in CHECKS)))
