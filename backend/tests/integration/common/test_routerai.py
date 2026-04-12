from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.app.common.routerai import (
    MODEL_CONTEXT_CACHE,
    ChatCompletionAccumulator,
    chat_completion_stream,
    create_embeddings,
    get_model_context_length,
)

# --- Хелперы для фейковых чанков ---


def make_chunk(content: str | None = None, tool_calls: list[Any] | None = None):
    delta = MagicMock()
    delta.content = content
    delta.tool_calls = tool_calls

    choice = MagicMock()
    choice.delta = delta

    chunk = MagicMock()
    chunk.choices = [choice]
    return chunk


def make_empty_chunk():
    chunk = MagicMock()
    chunk.choices = []
    return chunk


# --- Фейковый async iterator ---


async def async_iter(items: list[MagicMock]):
    for item in items:
        yield item


# --- Тесты chat_completion_stream ---


@pytest.mark.asyncio
async def test_stream_simple_text():
    chunks = [make_chunk("Hello"), make_chunk(", "), make_chunk("world!")]

    with patch("src.app.common.routerai.client") as mock_client:
        mock_client.chat.completions.create = AsyncMock(return_value=async_iter(chunks))

        result: list[str] = []
        async for token in chat_completion_stream([{"role": "user", "content": "hi"}]):
            result.append(token)

    assert "".join(result) == "Hello, world!"


@pytest.mark.asyncio
async def test_stream_skips_empty_choices():
    chunks = [make_empty_chunk(), make_chunk("ok")]

    with patch("src.app.common.routerai.client") as mock_client:
        mock_client.chat.completions.create = AsyncMock(return_value=async_iter(chunks))

        result: list[str] = []
        async for token in chat_completion_stream([{"role": "user", "content": "hi"}]):
            result.append(token)

    assert result == ["ok"]


@pytest.mark.asyncio
async def test_stream_with_accumulator_tool_calls():
    tc = MagicMock()
    tc.index = 0
    tc.id = "call_123"
    tc.function = MagicMock(name="get_weather", arguments='{"city":"Moscow"}')
    tc.function.name = "get_weather"
    tc.function.arguments = '{"city":"Moscow"}'

    chunks = [make_chunk(content=None, tool_calls=[tc])]

    with patch("src.app.common.routerai.client") as mock_client:
        mock_client.chat.completions.create = AsyncMock(return_value=async_iter(chunks))

        acc = ChatCompletionAccumulator()
        result: list[str] = []
        async for token in chat_completion_stream(
            [{"role": "user", "content": "weather?"}],
            accumulator=acc,
        ):
            result.append(token)

    assert result == []  # нет текста
    assert acc.has_tool_calls
    assert acc.tool_calls[0].name == "get_weather"


# --- Тесты create_embeddings ---


@pytest.mark.asyncio
async def test_create_embeddings():
    item = MagicMock()
    item.embedding = [0.1, 0.2, 0.3]

    resp = MagicMock()
    resp.data = [item]

    with patch("src.app.common.routerai.client") as mock_client:
        mock_client.embeddings.create = AsyncMock(return_value=resp)
        result = await create_embeddings(["test"])

    assert result == [[0.1, 0.2, 0.3]]


# --- Тесты get_model_context_length ---


@pytest.mark.asyncio
async def test_get_model_context_length_found():
    MODEL_CONTEXT_CACHE.clear()

    model_obj = MagicMock()
    model_obj.model_dump.return_value = {"id": "gpt-4", "context_length": 8192}

    resp = MagicMock()
    resp.data = [model_obj]

    with patch("src.app.common.routerai.client") as mock_client:
        mock_client.models.list = AsyncMock(return_value=resp)
        result = await get_model_context_length("gpt-4")

    assert result == 8192
    assert MODEL_CONTEXT_CACHE["gpt-4"] == 8192


@pytest.mark.asyncio
async def test_get_model_context_length_not_found():
    MODEL_CONTEXT_CACHE.clear()

    resp = MagicMock()
    resp.data = []

    with patch("src.app.common.routerai.client") as mock_client:
        mock_client.models.list = AsyncMock(return_value=resp)
        result = await get_model_context_length("unknown")

    assert result is None
