"""Thin async client for the RouterAI OpenAI-compatible API."""

from __future__ import annotations

import json
from collections.abc import AsyncGenerator
from dataclasses import dataclass, field

import httpx

from app.config import settings


def _build_base_url() -> str:
    return settings.routerai_base_url.rstrip("/")


_HEADERS = {
    "Authorization": f"Bearer {settings.routerai_api_key}",
    "Content-Type": "application/json",
}
_TIMEOUT = httpx.Timeout(60.0, connect=10.0)
_MODEL_CONTEXT_CACHE: dict[str, int] = {}


# ---------------------------------------------------------------------------
# Tool-calling support
# ---------------------------------------------------------------------------

@dataclass
class ToolCall:
    """A completed tool call parsed from streaming deltas."""
    id: str
    name: str
    arguments: str  # raw JSON string


class ChatCompletionAccumulator:
    """Collects content and tool_calls from an OpenAI streaming response."""

    def __init__(self) -> None:
        self.content_parts: list[str] = []
        self.tool_calls: list[ToolCall] = []
        self._tc_accum: dict[int, dict[str, str]] = {}

    def feed_delta(self, delta: dict) -> str | None:
        """Process a single delta dict. Returns content text if present."""
        content = delta.get("content")
        if content:
            self.content_parts.append(content)

        for tc in delta.get("tool_calls", []):
            idx = tc["index"]
            if idx not in self._tc_accum:
                self._tc_accum[idx] = {"id": "", "name": "", "arguments": ""}
            state = self._tc_accum[idx]
            if tc.get("id"):
                state["id"] = tc["id"]
            func = tc.get("function", {})
            if func.get("name"):
                state["name"] = func["name"]
            state["arguments"] += func.get("arguments", "")

        return content

    def finalize(self) -> None:
        """Build final tool_calls list from accumulated deltas."""
        self.tool_calls = [
            ToolCall(id=s["id"], name=s["name"], arguments=s["arguments"])
            for s in (self._tc_accum[i] for i in sorted(self._tc_accum))
        ]

    @property
    def full_content(self) -> str:
        return "".join(self.content_parts)

    @property
    def has_tool_calls(self) -> bool:
        return bool(self._tc_accum)


# ---------------------------------------------------------------------------
# API calls
# ---------------------------------------------------------------------------

async def create_embeddings(texts: list[str]) -> list[list[float]]:
    """Batch-embed texts. Returns one vector per input text."""
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        resp = await client.post(
            f"{_build_base_url()}/embeddings",
            headers=_HEADERS,
            json={
                "model": settings.routerai_embedding_model,
                "input": texts,
            },
        )
        resp.raise_for_status()
        data = resp.json()
    items = sorted(data["data"], key=lambda d: d["index"])
    return [item["embedding"] for item in items]


async def get_model_context_length(model: str) -> int | None:
    """Return the context window size for a model, if available."""
    if not model:
        return None
    if model in _MODEL_CONTEXT_CACHE:
        return _MODEL_CONTEXT_CACHE[model]

    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        resp = await client.get(f"{_build_base_url()}/models", headers=_HEADERS)
        resp.raise_for_status()
        data = resp.json()

    models: list[dict] = []
    if isinstance(data, dict):
        models = data.get("data", [])
    elif isinstance(data, list):
        for item in data:
            if isinstance(item, dict):
                models.extend(item.get("data", []))

    for item in models:
        if item.get("id") == model:
            context_length = item.get("context_length")
            if isinstance(context_length, int):
                _MODEL_CONTEXT_CACHE[model] = context_length
                return context_length
    return None


async def chat_completion_stream(
    messages: list[dict],
    model: str | None = None,
    tools: list[dict] | None = None,
    accumulator: ChatCompletionAccumulator | None = None,
) -> AsyncGenerator[str]:
    """Yield content deltas from a streaming chat completion.

    When *tools* and *accumulator* are provided, tool-call deltas are
    collected in the accumulator.  After iteration the caller can inspect
    ``accumulator.tool_calls``.

    Without these parameters the function behaves exactly as before
    (backward compatible).
    """
    model = model or settings.routerai_llm_model
    body: dict = {
        "model": model,
        "messages": messages,
        "stream": True,
    }
    if tools:
        body["tools"] = tools
        body["tool_choice"] = "auto"

    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        async with client.stream(
            "POST",
            f"{_build_base_url()}/chat/completions",
            headers=_HEADERS,
            json=body,
        ) as resp:
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                if not line.startswith("data: "):
                    continue
                payload = line.removeprefix("data: ").strip()
                if payload == "[DONE]":
                    break
                chunk = json.loads(payload)
                delta = chunk["choices"][0].get("delta", {})

                if accumulator:
                    content = accumulator.feed_delta(delta)
                    if content:
                        yield content
                else:
                    content = delta.get("content")
                    if content:
                        yield content

    if accumulator:
        accumulator.finalize()
