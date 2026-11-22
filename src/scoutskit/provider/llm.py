"""One JSON-returning LLM call that works across providers.

ScoutsKit's agent makes its decisions with this, so any configured provider,
including OpenRouter or a custom OpenAI-compatible endpoint, can be the brain.
Keys are only sent as headers to their own provider and never appear in errors.
"""

from __future__ import annotations

import asyncio
import json
import re
import time
from dataclasses import dataclass

import httpx

from .config import COMPATIBLE, ResolvedProvider

OPENAI_COMPATIBLE = {
    "openai": "https://api.openai.com/v1",
    "groq": "https://api.groq.com/openai/v1",
    "cerebras": "https://api.cerebras.ai/v1",
    "openrouter": "https://openrouter.ai/api/v1",
}
RETRY_STATUS = {429, 500, 502, 503, 504}
MAX_ATTEMPTS = 4
BACKOFF_S = (5, 15, 40)  # waits between attempts; a Retry-After header overrides, capped below
MAX_WAIT_S = 60
PARSE_RETRIES = 2  # a model that slips on the JSON (an unquoted string, say) is asked again, with what was wrong


class LLMError(Exception):
    """An LLM call failed after retries. The message never contains the API key."""


@dataclass
class LLMResult:
    data: dict
    prompt_tokens: int
    completion_tokens: int
    latency_ms: int


def parse_json(text: str) -> dict:
    """Parse a JSON object from model output, tolerating code fences and chatter."""
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip())
    start = cleaned.find("{")
    if start == -1:
        raise LLMError(f"model did not return a JSON object: {text[:120]!r}")
    try:
        value, _ = json.JSONDecoder().raw_decode(cleaned[start:])  # first object; ignores trailing text
    except json.JSONDecodeError as error:
        raise LLMError(f"model returned invalid JSON ({error.msg}); output was {len(text)} chars, ends: {text[-160:]!r}") from error
    if not isinstance(value, dict):
        raise LLMError("model returned JSON that is not an object")
    return value


def _retry_after(response: httpx.Response) -> float | None:
    value = response.headers.get("retry-after", "")
    try:
        return float(value) if value else None
    except ValueError:
        return None


def _retry_delay(response: httpx.Response) -> float | None:
    """Google reports how long a quota is locked in error.details[].retryDelay, e.g. '47961s'."""
    try:
        for detail in response.json().get("error", {}).get("details", []):
            delay = detail.get("retryDelay")
            if delay:
                return float(str(delay).rstrip("s"))
    except (ValueError, AttributeError, TypeError):
        pass
    return None


def _request(provider: ResolvedProvider, system: str, user: str) -> tuple[str, dict[str, str], dict]:
    kind, model = provider.kind, provider.api_model
    key = provider.api_key
    if kind == "google":
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
        body = {
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": [{"text": user}]}],
            "generationConfig": {"responseMimeType": "application/json", "temperature": 0},
        }
        return url, {"x-goog-api-key": key}, body
    if kind == "anthropic":
        body = {
            "model": model,
            "max_tokens": 4096,
            "temperature": 0,
            "system": system,
            "messages": [{"role": "user", "content": user}],
        }
        return "https://api.anthropic.com/v1/messages", {"x-api-key": key, "anthropic-version": "2023-06-01"}, body
    if kind in OPENAI_COMPATIBLE or kind == COMPATIBLE:
        body = {"model": model, "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]}
        if kind == COMPATIBLE:
            # Custom endpoints: don't assume json_object or temperature are supported (reasoning models
            # reject or ignore them); the lenient parser handles plain-text JSON. Leave room to think.
            body["max_tokens"] = 4096
            body.update(provider.extra_body)
            base = (provider.base_url or "").rstrip("/")
        else:
            body["response_format"] = {"type": "json_object"}
            if kind != "openai":  # some OpenAI models reject a non-default temperature
                body["temperature"] = 0
            body.update(provider.extra_body)
            base = OPENAI_COMPATIBLE[kind]
        return f"{base}/chat/completions", {"Authorization": f"Bearer {key}"}, body
    raise LLMError(f"provider {kind!r} is not supported for agent decisions")


def _read(kind: str, payload: dict) -> tuple[str, int, int]:
    try:
        if kind == "google":
            parts = payload["candidates"][0]["content"]["parts"]
            usage = payload.get("usageMetadata", {})
            text = "".join(part.get("text", "") for part in parts)
            return text, usage.get("promptTokenCount", 0), usage.get("candidatesTokenCount", 0)
        if kind == "anthropic":
            usage = payload.get("usage", {})
            text = "".join(block.get("text", "") for block in payload["content"])
            return text, usage.get("input_tokens", 0), usage.get("output_tokens", 0)
        usage = payload.get("usage", {})
        text = payload["choices"][0]["message"]["content"] or ""
        return text, usage.get("prompt_tokens", 0), usage.get("completion_tokens", 0)
    except (KeyError, IndexError, TypeError) as error:
        raise LLMError(f"unexpected response shape from {kind}") from error


async def complete_json(
    provider: ResolvedProvider,
    system: str,
    user: str,
    *,
    client: httpx.AsyncClient | None = None,
    timeout: float = 90,
) -> LLMResult:
    kind = provider.kind
    url, headers, body = _request(provider, system, user)
    http = client or httpx.AsyncClient(timeout=timeout)
    started = time.perf_counter()
    last = "no attempt made"
    bad_replies = 0
    try:
        for attempt in range(MAX_ATTEMPTS):
            wait = BACKOFF_S[min(attempt, len(BACKOFF_S) - 1)]
            try:
                response = await http.post(url, headers=headers, json=body)
            except httpx.HTTPError as error:
                last = f"network error ({type(error).__name__})"
            else:
                if response.status_code == 200:
                    text, prompt_tokens, completion_tokens = _read(kind, response.json())
                    try:
                        data = parse_json(text)
                    except LLMError as error:
                        if bad_replies >= PARSE_RETRIES:
                            raise
                        bad_replies += 1
                        last = "the reply was not valid JSON"
                        url, headers, body = _request(provider, system, f"{user}\n\nYour previous reply was not valid JSON ({error}). Reply with ONLY one valid JSON object: every string in double quotes.")
                        continue
                    return LLMResult(data, prompt_tokens, completion_tokens, int((time.perf_counter() - started) * 1000))
                last = f"HTTP {response.status_code}"
                if response.status_code not in RETRY_STATUS:
                    raise LLMError(f"{kind} call failed: {last}")
                wait = _retry_after(response) or _retry_delay(response) or BACKOFF_S[min(attempt, len(BACKOFF_S) - 1)]
                if response.status_code == 429 and wait > MAX_WAIT_S:
                    raise LLMError(f"{kind} quota exhausted (retry in about {wait / 3600:.1f} h)")
            if attempt < MAX_ATTEMPTS - 1:
                await asyncio.sleep(min(wait, MAX_WAIT_S))
    finally:
        if client is None:
            await http.aclose()
    raise LLMError(f"{kind} call failed after {MAX_ATTEMPTS} attempts: {last}")
