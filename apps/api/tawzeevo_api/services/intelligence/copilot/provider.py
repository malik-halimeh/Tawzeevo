"""Groq chat-completions adapter (D-089): plain httpx, key-gated, bounded by a timeout.

The API is OpenAI-compatible (`/openai/v1/chat/completions` with function tools). Nothing about
the request or the response body is logged; failures surface as `CopilotProviderError` with a
short reason code only, so the caller can answer with a controlled error.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

import httpx

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"


class CopilotProviderError(Exception):
    """A provider failure; `str(exc)` is a short code, never provider content."""


@dataclass(frozen=True)
class ToolCall:
    id: str
    name: str
    arguments: str


@dataclass(frozen=True)
class ProviderReply:
    content: str | None
    tool_calls: list[ToolCall]
    raw_message: dict[str, Any]  # echoed back to the provider as the assistant turn


class ChatProvider(Protocol):
    def complete(
        self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]
    ) -> ProviderReply: ...


class GroqProvider:
    def __init__(self, api_key: str, model: str, timeout: float) -> None:
        self._api_key = api_key
        self.model = model
        self.timeout = timeout

    def complete(
        self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]
    ) -> ProviderReply:
        payload = {
            "model": self.model,
            "messages": messages,
            "tools": tools,
            "tool_choice": "auto",
            "temperature": 0,
        }
        try:
            response = httpx.post(
                GROQ_URL,
                json=payload,
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                },
                timeout=self.timeout,
            )
        except httpx.TimeoutException as exc:
            raise CopilotProviderError("TIMEOUT") from exc
        except httpx.HTTPError as exc:
            raise CopilotProviderError("CONNECTION") from exc
        if response.status_code == 429:
            raise CopilotProviderError("PROVIDER_RATE_LIMITED")
        if response.status_code != 200:
            raise CopilotProviderError(f"STATUS_{response.status_code}")
        return parse_reply(response)


def parse_reply(response: httpx.Response) -> ProviderReply:
    try:
        message = response.json()["choices"][0]["message"]
        calls = [
            ToolCall(
                id=str(call["id"]),
                name=str(call["function"]["name"]),
                arguments=str(call["function"].get("arguments") or "{}"),
            )
            for call in message.get("tool_calls") or []
        ]
        content = message.get("content")
        if content is not None and not isinstance(content, str):
            raise TypeError("content")
    except (KeyError, IndexError, ValueError, TypeError) as exc:
        raise CopilotProviderError("MALFORMED_RESPONSE") from exc
    raw: dict[str, Any] = {"role": "assistant", "content": content}
    if calls:
        raw["tool_calls"] = [
            {
                "id": call.id,
                "type": "function",
                "function": {"name": call.name, "arguments": call.arguments},
            }
            for call in calls
        ]
    return ProviderReply(content=content, tool_calls=calls, raw_message=raw)
