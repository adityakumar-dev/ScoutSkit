"""Check every configured provider and choose one that works.

The first run (or `scoutskit providers --check`) tests each key; results are
cached for a day so later runs do not repeat the calls. The cache holds
statuses only, never keys.
"""

from __future__ import annotations

import asyncio
import json
import os
import time
from dataclasses import asdict
from pathlib import Path

import httpx

from .config import ConfigError, Settings
from .connect import TIMEOUT_S, ProviderCheck, check_provider

CACHE_TTL_S = 24 * 3600
RETRY_TTL_S = 10 * 60  # a cache holding a real failure (timeout, 503, ...) is re-checked after 10 minutes


def _cache_path(settings: Settings) -> Path:
    return settings.root / ".scoutskit" / "provider_status.json"


async def check_all(settings: Settings) -> list[ProviderCheck]:
    """Test every provider concurrently and record the outcome on each config."""
    async with httpx.AsyncClient(timeout=TIMEOUT_S) as client:
        results = await asyncio.gather(
            *(
                check_provider(
                    name, cfg, os.environ.get(cfg.api_key_env, "").strip() or None, client=client
                )
                for name, cfg in settings.providers.items()
            )
        )
    for result in results:
        settings.providers[result.provider].is_working = result.ok
    _save_cache(settings, results)
    return list(results)


def _save_cache(settings: Settings, results: list[ProviderCheck]) -> None:
    path = _cache_path(settings)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"checked_at": time.time(), "results": [asdict(r) for r in results]}, indent=2))


def load_cache(settings: Settings) -> list[ProviderCheck] | None:
    """Return fresh cached results, or None if missing, stale or unreadable."""
    try:
        data = json.loads(_cache_path(settings).read_text())
        results = [ProviderCheck(**row) for row in data["results"]]
        steady = all(r.ok or r.detail.startswith("no key") for r in results)  # a missing key does not heal by itself
        if time.time() - float(data["checked_at"]) > (CACHE_TTL_S if steady else RETRY_TTL_S):
            return None
    except (OSError, ValueError, KeyError, TypeError):
        return None
    configured = set(settings.providers)
    return results if {r.provider for r in results} == configured else None


def _usable(settings: Settings, check: ProviderCheck) -> bool:
    return check.ok and check.model_found is not False


def usable_order(settings: Settings, results: list[ProviderCheck], preferred: str | None = None) -> list[str]:
    """Every usable provider: preferred/default first, then config order."""
    first = preferred or settings.default_provider
    order = [first, *(n for n in settings.providers if n != first)]
    by_name = {r.provider: r for r in results}
    return [n for n in order if n in by_name and _usable(settings, by_name[n])]


def choose_provider(
    settings: Settings, results: list[ProviderCheck], preferred: str | None = None
) -> tuple[str, str | None]:
    """Pick the first usable provider: preferred/default first, then config order.

    Returns (name, note); note says why a fallback was used, or None.
    """
    first = preferred or settings.default_provider
    usable = usable_order(settings, results, preferred)
    if not usable:
        raise ConfigError(
            "No working LLM provider. Run `scoutskit providers --check` to see why each one failed."
        )
    name = usable[0]
    if name == first:
        return name, None
    detail = next((r.detail for r in results if r.provider == first), "not checked")
    return name, f"{first!r} unavailable ({detail}); using {name!r}"


async def _results(settings: Settings, force: bool) -> list[ProviderCheck]:
    results = None if force else load_cache(settings)
    if results is None:
        return await check_all(settings)
    for result in results:
        settings.providers[result.provider].is_working = result.ok
    return results


async def ensure_provider(settings: Settings, preferred: str | None = None, *, force: bool = False) -> tuple[str, str | None]:
    """Entry point for a run: use cached results when fresh, otherwise test every key first."""
    return choose_provider(settings, await _results(settings, force), preferred)


async def ensure_providers(
    settings: Settings, preferred: str | None = None, *, force: bool = False
) -> tuple[list[str], str | None]:
    """Like ensure_provider, but returns every usable provider in fallback order."""
    results = await _results(settings, force)
    _, note = choose_provider(settings, results, preferred)
    return usable_order(settings, results, preferred), note
