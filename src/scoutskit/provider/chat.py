"""LangChain chat models built from a resolved provider.

Every OpenAI-compatible provider (OpenAI, Groq, Cerebras, OpenRouter, Google's compatible
endpoint, NVIDIA NIM, a local server) goes through ChatOpenAI with its own base_url; only
Anthropic needs its own class. Native tool calling is used wherever the model supports it.
"""

from __future__ import annotations

from langchain_core.language_models import BaseChatModel

from .config import COMPATIBLE, ResolvedProvider

BASE_URLS = {
    "openai": None,
    "groq": "https://api.groq.com/openai/v1",
    "cerebras": "https://api.cerebras.ai/v1",
    "openrouter": "https://openrouter.ai/api/v1",
    "google": "https://generativelanguage.googleapis.com/v1beta/openai/",
}


def make_chat_model(provider: ResolvedProvider) -> BaseChatModel:
    if provider.kind == "anthropic":
        from langchain_anthropic import ChatAnthropic

        return ChatAnthropic(
            model=provider.api_model, api_key=provider.api_key, temperature=0.2, max_tokens=provider.max_tokens, max_retries=1, timeout=120
        )
    from langchain_openai import ChatOpenAI

    base_url = provider.base_url if provider.kind == COMPATIBLE else BASE_URLS.get(provider.kind)
    options: dict = dict(model=provider.api_model, api_key=provider.api_key, base_url=base_url, max_retries=1, timeout=120, max_tokens=provider.max_tokens)
    if provider.kind != "openai":  # some OpenAI models reject a non-default temperature
        options["temperature"] = 0.2
    if provider.extra_body:
        options["extra_body"] = provider.extra_body
    return ChatOpenAI(**options)
