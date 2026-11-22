"""The JSON client: a model that slips on the JSON gets asked again; one that keeps failing gets a clear error."""

import httpx
import pytest

from scoutskit.provider.config import ResolvedProvider
from scoutskit.provider.llm import LLMError, complete_json

PROVIDER = ResolvedProvider(name="t", model_name="openai/x", api_key="k", kind="openai", api_model="x")
GOOD = '{"goal": "Search for SIH problem statements", "item_name": "problem statement"}'
UNQUOTED = '{"goal": Search for SIH problem statements, "item_name": "problem statement"}'


def reply(text: str) -> httpx.Response:
    return httpx.Response(200, json={"choices": [{"message": {"content": text}}], "usage": {"prompt_tokens": 5, "completion_tokens": 7}})


def client(*texts: str):
    requests = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request.read().decode())
        return reply(texts[min(len(requests) - 1, len(texts) - 1)])

    return httpx.AsyncClient(transport=httpx.MockTransport(handler)), requests


async def test_an_unquoted_string_is_asked_again_with_what_was_wrong():
    http, requests = client(UNQUOTED, GOOD)
    result = await complete_json(PROVIDER, "system", "plan this", client=http)
    assert result.data["item_name"] == "problem statement" and len(requests) == 2
    assert "previous reply was not valid JSON" in requests[1] and "plan this" in requests[1]


async def test_a_model_that_keeps_failing_gets_a_clear_error_after_a_few_tries():
    http, requests = client(UNQUOTED)
    with pytest.raises(LLMError, match="invalid JSON"):
        await complete_json(PROVIDER, "system", "plan this", client=http)
    assert len(requests) == 3  # the first reply and two retries
