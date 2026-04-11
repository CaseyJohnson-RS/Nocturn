"""Thin async client for the RouterAI OpenAI-compatible API (SDK-based)."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from dataclasses import dataclass
from typing import Any

from openai import AsyncOpenAI

from app.config import settings

# ---------------------------------------------------------------------------
# region Client

client = AsyncOpenAI(
    api_key=settings.routerai_api_key,
    base_url=settings.routerai_base_url.rstrip("/") + "/v1",
)

# endregion
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# region Cache

MODEL_CONTEXT_CACHE: dict[str, int] = {}

# endregion
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# region Tool-calling support


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: str


class ChatCompletionAccumulator:
    def __init__(self) -> None:
        self.content_parts: list[str] = []
        self.tool_calls: list[ToolCall] = []

    def feed_delta(self, delta: Any) -> str | None:
        content = getattr(delta, "content", None)

        if isinstance(content, str):
            self.content_parts.append(content)

        tool_calls = getattr(delta, "tool_calls", None)

        if tool_calls:
            for tc in tool_calls:
                idx = tc.index if hasattr(tc, "index") else 0

                while len(self.tool_calls) <= idx:
                    self.tool_calls.append(ToolCall("", "", ""))

                self.tool_calls[idx].id = getattr(tc, "id", "") or self.tool_calls[idx].id

                func = getattr(tc, "function", None)
                if func:
                    if getattr(func, "name", None):
                        self.tool_calls[idx].name = func.name

                    if getattr(func, "arguments", None):
                        self.tool_calls[idx].arguments += func.arguments

        return content

    @property
    def full_content(self) -> str:
        return "".join(self.content_parts)

    @property
    def has_tool_calls(self) -> bool:
        return bool(self.tool_calls)


# endregion
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# region API calls


async def create_embeddings(texts: list[str]) -> list[list[float]]:
    resp = await client.embeddings.create(
        model=settings.routerai_embedding_model,
        input=texts,
    )
    return [item.embedding for item in resp.data]


async def get_model_context_length(model: str) -> int | None:
    if not model:
        return None

    if model in MODEL_CONTEXT_CACHE:
        return MODEL_CONTEXT_CACHE[model]

    resp = await client.models.list()

    models: list[dict[str, Any]] = []

    for m in resp.data:
        models.append(m.model_dump())

    for item in models:
        if item.get("id") == model:
            ctx = item.get("context_length")
            if isinstance(ctx, int):
                MODEL_CONTEXT_CACHE[model] = ctx
                return ctx

    return None


# endregion
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# region Streaming chat

# FIXME: check types!
async def chat_completion_stream(
    messages: list[dict[str, Any]],
    model: str | None = None,
    tools: list[dict[str, Any]] | None = None,
    accumulator: ChatCompletionAccumulator | None = None,
) -> AsyncGenerator[str, None]:

    model = model or settings.routerai_llm_model

    kwargs: dict[str, Any] = dict(
        model=model,
        messages=messages,
        stream=True,
    )
    if tools:
        kwargs["tools"] = tools
        kwargs["tool_choice"] = "auto"

    stream = await client.chat.completions.create(**kwargs) # type: ignore

    async for chunk in stream: # type: ignore
        if not chunk.choices: # type: ignore
            continue

        delta = chunk.choices[0].delta # type: ignore
        if delta is None:
            continue

        if accumulator:
            content = accumulator.feed_delta(delta)
            if isinstance(content, str):
                yield content
            continue

        content = getattr(delta, "content", None) # type: ignore
        if isinstance(content, str):
            yield content


# endregion
# ---------------------------------------------------------------------------
