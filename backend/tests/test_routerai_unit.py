"""Unit tests for the RouterAI API client."""

import httpx
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from app.common.routerai import (
    ChatCompletionAccumulator,
    ToolCall,
    create_embeddings,
    chat_completion_stream,
    get_model_context_length,
)

_FAKE_REQUEST = httpx.Request("POST", "http://test/embeddings")


# --- create_embeddings ---

class TestCreateEmbeddings:
    async def test_returns_embeddings_in_input_order(self):
        """Embeddings must be returned in the same order as input texts,
        even if the API returns them out of order."""
        response_data = {
            "data": [
                {"index": 1, "embedding": [0.2, 0.2]},
                {"index": 0, "embedding": [0.1, 0.1]},
            ]
        }
        mock_response = httpx.Response(200, json=response_data, request=_FAKE_REQUEST)

        with patch("app.common.routerai.httpx.AsyncClient") as MockClient:
            instance = AsyncMock()
            instance.post.return_value = mock_response
            instance.__aenter__ = AsyncMock(return_value=instance)
            instance.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = instance

            result = await create_embeddings(["text0", "text1"])

        assert result == [[0.1, 0.1], [0.2, 0.2]]

    async def test_single_text(self):
        response_data = {
            "data": [{"index": 0, "embedding": [0.5, 0.6, 0.7]}]
        }
        mock_response = httpx.Response(200, json=response_data, request=_FAKE_REQUEST)

        with patch("app.common.routerai.httpx.AsyncClient") as MockClient:
            instance = AsyncMock()
            instance.post.return_value = mock_response
            instance.__aenter__ = AsyncMock(return_value=instance)
            instance.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = instance

            result = await create_embeddings(["hello"])

        assert result == [[0.5, 0.6, 0.7]]

    async def test_sends_correct_request(self):
        response_data = {"data": [{"index": 0, "embedding": [0.1]}]}
        mock_response = httpx.Response(200, json=response_data, request=_FAKE_REQUEST)

        with patch("app.common.routerai.httpx.AsyncClient") as MockClient:
            instance = AsyncMock()
            instance.post.return_value = mock_response
            instance.__aenter__ = AsyncMock(return_value=instance)
            instance.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = instance

            await create_embeddings(["test input"])

            call_kwargs = instance.post.call_args
            assert call_kwargs.args[0] == "https://routerai.ru/api/v1/embeddings"
            body = call_kwargs.kwargs["json"]
            assert body["input"] == ["test input"]
            assert "model" in body

    async def test_raises_on_http_error(self):
        mock_response = httpx.Response(500, text="Internal Server Error",
                                       request=_FAKE_REQUEST)

        with patch("app.common.routerai.httpx.AsyncClient") as MockClient:
            instance = AsyncMock()
            instance.post.return_value = mock_response
            instance.__aenter__ = AsyncMock(return_value=instance)
            instance.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = instance

            with pytest.raises(httpx.HTTPStatusError):
                await create_embeddings(["fail"])


    async def test_get_model_context_length(self):
        response_data = {
            "data": [
                {"id": "deepseek/deepseek-chat-v3.1", "context_length": 8192},
            ]
        }
        mock_response = httpx.Response(200, json=response_data, request=_FAKE_REQUEST)

        with patch("app.common.routerai.httpx.AsyncClient") as MockClient:
            instance = AsyncMock()
            instance.get.return_value = mock_response
            instance.__aenter__ = AsyncMock(return_value=instance)
            instance.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = instance

            context_length = await get_model_context_length("deepseek/deepseek-chat-v3.1")

        assert context_length == 8192


# --- chat_completion_stream ---

class TestChatCompletionStream:
    async def test_yields_content_deltas(self):
        lines = [
            "data: " + '{"choices":[{"delta":{"role":"assistant"}}]}',
            "data: " + '{"choices":[{"delta":{"content":"Hello"}}]}',
            "data: " + '{"choices":[{"delta":{"content":" world"}}]}',
            "data: [DONE]",
        ]

        mock_resp = AsyncMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.aiter_lines = self._async_line_iter(lines)
        mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
        mock_resp.__aexit__ = AsyncMock(return_value=False)

        mock_client = AsyncMock()
        mock_client.stream = MagicMock(return_value=mock_resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("app.common.routerai.httpx.AsyncClient", return_value=mock_client):
            chunks = []
            async for c in chat_completion_stream([{"role": "user", "content": "hi"}]):
                chunks.append(c)

        assert chunks == ["Hello", " world"]

    async def test_skips_non_data_lines(self):
        lines = [
            ": keepalive",
            "",
            "data: " + '{"choices":[{"delta":{"content":"ok"}}]}',
            "data: [DONE]",
        ]

        mock_resp = AsyncMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.aiter_lines = self._async_line_iter(lines)
        mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
        mock_resp.__aexit__ = AsyncMock(return_value=False)

        mock_client = AsyncMock()
        mock_client.stream = MagicMock(return_value=mock_resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("app.common.routerai.httpx.AsyncClient", return_value=mock_client):
            chunks = []
            async for c in chat_completion_stream([{"role": "user", "content": "hi"}]):
                chunks.append(c)

        assert chunks == ["ok"]

    async def test_sends_correct_request(self):
        lines = ["data: [DONE]"]

        mock_resp = AsyncMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.aiter_lines = self._async_line_iter(lines)
        mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
        mock_resp.__aexit__ = AsyncMock(return_value=False)

        mock_client = AsyncMock()
        mock_client.stream = MagicMock(return_value=mock_resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        messages = [{"role": "user", "content": "hello"}]

        with patch("app.common.routerai.httpx.AsyncClient", return_value=mock_client):
            async for _ in chat_completion_stream(messages, model="test-model"):
                pass

        call_kwargs = mock_client.stream.call_args
        assert call_kwargs.args[0] == "POST"
        assert "/chat/completions" in call_kwargs.args[1]
        body = call_kwargs.kwargs["json"]
        assert body["model"] == "test-model"
        assert body["messages"] == messages
        assert body["stream"] is True

    async def test_accumulator_collects_tool_calls(self):
        """When tools and accumulator are passed, tool_calls are collected."""
        lines = [
            "data: " + '{"choices":[{"delta":{"tool_calls":[{"index":0,"id":"tc1","type":"function","function":{"name":"get_note","arguments":"{\\"n"}}]}}]}',
            "data: " + '{"choices":[{"delta":{"tool_calls":[{"index":0,"function":{"arguments":"ote_id\\":\\"abc\\"}"}}]}}]}',
            "data: [DONE]",
        ]

        mock_resp = AsyncMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.aiter_lines = self._async_line_iter(lines)
        mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
        mock_resp.__aexit__ = AsyncMock(return_value=False)

        mock_client = AsyncMock()
        mock_client.stream = MagicMock(return_value=mock_resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        accumulator = ChatCompletionAccumulator()
        tools = [{"type": "function", "function": {"name": "get_note"}}]

        with patch("app.common.routerai.httpx.AsyncClient", return_value=mock_client):
            chunks = []
            async for c in chat_completion_stream(
                [{"role": "user", "content": "hi"}],
                tools=tools,
                accumulator=accumulator,
            ):
                chunks.append(c)

        assert chunks == []  # No content deltas, only tool calls
        assert len(accumulator.tool_calls) == 1
        tc = accumulator.tool_calls[0]
        assert tc.id == "tc1"
        assert tc.name == "get_note"
        assert '"note_id":"abc"' in tc.arguments

    @staticmethod
    def _async_line_iter(lines):
        async def _iter():
            for line in lines:
                yield line
        return _iter


# --- ChatCompletionAccumulator ---

class TestAccumulator:
    def test_content_accumulation(self):
        acc = ChatCompletionAccumulator()
        assert acc.feed_delta({"content": "Hello"}) == "Hello"
        assert acc.feed_delta({"content": " world"}) == " world"
        acc.finalize()
        assert acc.full_content == "Hello world"
        assert not acc.has_tool_calls
        assert acc.tool_calls == []

    def test_tool_call_accumulation(self):
        acc = ChatCompletionAccumulator()
        acc.feed_delta({
            "tool_calls": [
                {"index": 0, "id": "tc_1", "function": {"name": "get_note", "arguments": '{"no'}},
            ]
        })
        acc.feed_delta({
            "tool_calls": [
                {"index": 0, "function": {"arguments": 'te_id":"abc"}'}},
            ]
        })
        assert acc.has_tool_calls
        acc.finalize()
        assert len(acc.tool_calls) == 1
        assert acc.tool_calls[0].id == "tc_1"
        assert acc.tool_calls[0].name == "get_note"
        assert acc.tool_calls[0].arguments == '{"note_id":"abc"}'

    def test_mixed_content_and_tools(self):
        acc = ChatCompletionAccumulator()
        acc.feed_delta({"content": "Let me search"})
        acc.feed_delta({
            "tool_calls": [
                {"index": 0, "id": "tc_1", "function": {"name": "search_notes", "arguments": "{}"}},
            ]
        })
        acc.finalize()
        assert acc.full_content == "Let me search"
        assert len(acc.tool_calls) == 1
