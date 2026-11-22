"""Check that one provider's API key works.

Uses free, read-only endpoints (model listing, or OpenRouter's key-info call),
so no tokens are spent. The key is only ever sent as a header to the provider
it belongs to and is never included in results or error text.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

import httpx

from .config import ProviderConfig

TIMEOUT_S = 15.0

# kind -> (url, auth header style, query params). Model listing unless noted.
_ENDPOINTS: dict[str, tuple[str, str, dict[str, str]]] = {
    "anthropic": ("https://api.anthropic.com/v1/models", "x-api-key", {"limit": "1000"}),
    "openai": ("https://api.openai.com/v1/models", "bearer", {}),
    "google": ("https://generativelanguage.googleapis.com/v1beta/models", "x-goog-api-key", {"pageSize": "1000"}),
    "groq": ("https://api.groq.com/openai/v1/models", "bearer", {}),
    "cerebras": ("https://api.cerebras.ai/v1/models", "bearer", {}),
    # /models is public on OpenRouter, so it cannot validate a key; /key can.
    "openrouter": ("https://openrouter.ai/api/v1/key", "bearer", {}),
}


@dataclass
class ProviderCheck:
    provider: str
    ok: bool
    detail: str
    latency_ms: int | None = None
    model_found: bool | None = None  # None = not checkable for this provider


def _headers(style: str, key: str) -> dict[str, str]:
    if style == "bearer":
        return {"Authorization": f"Bearer {key}"}
    if style == "x-api-key":
        return {"x-api-key": key, "anthropic-version": "2023-06-01"}
    return {style: key}


def _model_ids(payload: dict) -> set[str]:
    rows = payload.get("data") or payload.get("models") or []
    ids = {str(row.get("id") or row.get("name") or "") for row in rows if isinstance(row, dict)}
    # Google lists "models/gemini-2.5-flash"
    return {i.removeprefix("models/") for i in ids if i}


def _explain(status: int) -> str:
    if status in (401, 403):
        return f"key rejected (HTTP {status})"
    if status == 429:
        return "rate limited or out of quota (HTTP 429)"
    return f"unexpected response (HTTP {status})"


async def _probe_model(
    name: str, config: ProviderConfig, api_key: str, http: httpx.AsyncClient, listed_ms: int
) -> ProviderCheck:
    body = {"model": config.api_model, "messages": [{"role": "user", "content": "Reply with the word ok"}], "max_tokens": 8, **config.extra_body}
    started = time.perf_counter()
    try:
        response = await http.post(
            f"{(config.base_url or '').rstrip('/')}/chat/completions", headers=_headers("bearer", api_key), json=body, timeout=45
        )
    except httpx.TimeoutException:
        return ProviderCheck(name, False, "listed, but the model call timed out", listed_ms, False)
    except httpx.HTTPError as error:
        return ProviderCheck(name, False, f"listed, but the model call failed ({type(error).__name__})", listed_ms, False)
    took = int((time.perf_counter() - started) * 1000)
    if response.status_code != 200:
        return ProviderCheck(name, False, f"listed, but the model call failed (HTTP {response.status_code})", took, False)
    return ProviderCheck(name, True, "key works, model answered", took, True)


async def check_provider(
    name: str, config: ProviderConfig, api_key: str | None, *, client: httpx.AsyncClient | None = None
) -> ProviderCheck:
    if not api_key:
        return ProviderCheck(name, False, f"no key set ({config.api_key_env})")
    endpoint = (
        (f"{config.base_url.rstrip('/')}/models", "bearer", {}) if config.base_url else _ENDPOINTS.get(config.kind)
    )
    if endpoint is None:
        return ProviderCheck(name, False, f"no key check available for {config.kind!r}")

    url, style, params = endpoint
    owns_client = client is None
    http = client or httpx.AsyncClient(timeout=TIMEOUT_S)
    started = time.perf_counter()
    try:
        response = await http.get(url, headers=_headers(style, api_key), params=params)
    except httpx.TimeoutException:
        return ProviderCheck(name, False, "timed out")
    except httpx.HTTPError as error:
        return ProviderCheck(name, False, f"network error ({type(error).__name__})")
    finally:
        if owns_client:
            await http.aclose()
    latency = int((time.perf_counter() - started) * 1000)

    if response.status_code != 200:
        return ProviderCheck(name, False, _explain(response.status_code), latency)

    if config.kind == "openrouter":  # the model id (e.g. openrouter/auto) is not listed; judge by the account
        try:
            info = response.json().get("data", {})
        except ValueError:
            info = {}
        remaining = info.get("limit_remaining")
        if info.get("is_free_tier") and not config.model.endswith(":free"):
            return ProviderCheck(name, False, "key valid, but free-tier account has no credits (add credits or use a ':free' model)", latency)
        if remaining is not None and remaining <= 0:
            return ProviderCheck(name, False, "key valid, but its spending limit is used up", latency)
        return ProviderCheck(name, True, "key accepted", latency)

    try:
        ids = _model_ids(response.json())
    except ValueError:
        return ProviderCheck(name, True, "key accepted (model list unreadable)", latency)
    wanted = config.api_model
    if wanted in ids:
        if config.base_url:  # listed is not live: confirm with one tiny call
            return await _probe_model(name, config, api_key, http, latency)
        return ProviderCheck(name, True, "key works, model found", latency, True)
    return ProviderCheck(name, True, f"key works, but model {wanted!r} not in the provider's list", latency, False)
