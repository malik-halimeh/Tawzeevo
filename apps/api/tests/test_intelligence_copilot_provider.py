"""D-089 Groq adapter: request shape, key only in the header, controlled failures (timeout,
connection, 429, 5xx, malformed body) and tool-call parsing. The network is always stubbed."""

from __future__ import annotations

import httpx
import pytest

from tawzeevo_api.services.intelligence.copilot import provider as provider_module
from tawzeevo_api.services.intelligence.copilot.provider import (
    GROQ_URL,
    CopilotProviderError,
    GroqProvider,
)


def _response(status: int, body: object) -> httpx.Response:
    return httpx.Response(status, json=body, request=httpx.Request("POST", GROQ_URL))


def test_request_shape_and_tool_call_parsing(monkeypatch):
    seen: dict[str, object] = {}

    def fake_post(url, json, headers, timeout):  # noqa: A002 - mirrors httpx.post
        seen.update(url=url, json=json, headers=headers, timeout=timeout)
        return _response(
            200,
            {
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": None,
                            "tool_calls": [
                                {
                                    "id": "call_1",
                                    "type": "function",
                                    "function": {
                                        "name": "get_daily_priorities",
                                        "arguments": '{"limit": 3}',
                                    },
                                }
                            ],
                        }
                    }
                ]
            },
        )

    monkeypatch.setattr(provider_module.httpx, "post", fake_post)
    reply = GroqProvider("secret-key", "test-model", 5.0).complete(
        [{"role": "user", "content": "hi"}], [{"type": "function", "function": {"name": "x"}}]
    )
    assert seen["url"] == GROQ_URL and seen["timeout"] == 5.0
    assert seen["headers"]["Authorization"] == "Bearer secret-key"  # type: ignore[index]
    body = seen["json"]
    assert body["model"] == "test-model" and body["temperature"] == 0  # type: ignore[index]
    assert "secret-key" not in str(body)
    assert [c.name for c in reply.tool_calls] == ["get_daily_priorities"]
    assert reply.raw_message["tool_calls"][0]["id"] == "call_1"


@pytest.mark.parametrize(
    ("outcome", "code"),
    [
        (httpx.ReadTimeout("slow"), "TIMEOUT"),
        (httpx.ConnectError("down"), "CONNECTION"),
        (_response(429, {}), "PROVIDER_RATE_LIMITED"),
        (_response(500, {"error": "boom"}), "STATUS_500"),
        (_response(401, {"error": "bad key"}), "STATUS_401"),
        (_response(200, {"unexpected": True}), "MALFORMED_RESPONSE"),
        (_response(200, {"choices": [{"message": {"content": 5}}]}), "MALFORMED_RESPONSE"),
    ],
)
def test_failures_are_controlled_codes(monkeypatch, outcome, code):
    def fake_post(*_args, **_kwargs):
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    monkeypatch.setattr(provider_module.httpx, "post", fake_post)
    with pytest.raises(CopilotProviderError) as caught:
        GroqProvider("k", "m", 1.0).complete([], [])
    assert str(caught.value) == code


def test_a_call_without_tools_sends_no_tool_fields(monkeypatch):
    """Contextual explanations (D-091) supply their facts and offer the model no tools."""
    seen: dict[str, object] = {}

    def fake_post(url, json, headers, timeout):  # noqa: A002 - mirrors httpx.post
        seen.update(json=json)
        return _response(200, {"choices": [{"message": {"role": "assistant", "content": "ok"}}]})

    monkeypatch.setattr(provider_module.httpx, "post", fake_post)
    reply = GroqProvider("secret-key", "test-model", 5.0).complete(
        [{"role": "user", "content": "hi"}], []
    )
    body = seen["json"]
    assert "tools" not in body and "tool_choice" not in body  # type: ignore[operator]
    assert reply.content == "ok" and reply.tool_calls == []
