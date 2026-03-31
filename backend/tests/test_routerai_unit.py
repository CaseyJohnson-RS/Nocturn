"""Unit tests for the RouterAI API client."""

import httpx
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from app.common.routerai import create_embeddings, chat_completion_stream

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
            assert "/embeddings" in call_kwargs.args[0]
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

    @staticmethod
    def _async_line_iter(lines):
        async def _iter():
            for line in lines:
                yield line
        return _iter
