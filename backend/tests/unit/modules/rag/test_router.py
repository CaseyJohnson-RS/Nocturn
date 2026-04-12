"""Unit tests for RAG router."""

import uuid
from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from src.app.middleware.auth import get_current_user
from src.app.modules.rag.router import get_rag_service, router
from src.app.modules.rag.schemas import SearchResponse, SearchResult

SEARCH = "/api/rag/search"


@pytest.fixture()
def user_id() -> uuid.UUID:
    return uuid.uuid4()


@pytest.fixture()
def mock_service() -> AsyncMock:
    return AsyncMock()


@pytest.fixture()
def app(mock_service: AsyncMock, user_id: uuid.UUID) -> FastAPI:
    test_app = FastAPI()
    test_app.include_router(router)
    test_app.dependency_overrides[get_rag_service] = lambda: mock_service
    test_app.dependency_overrides[get_current_user] = lambda: MagicMock(id=user_id, role="user")
    return test_app


@pytest.fixture()
async def client(app: FastAPI) -> AsyncGenerator[AsyncClient, None]:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


class TestSearch:
    @pytest.mark.anyio()
    async def test_success(
        self, client: AsyncClient, mock_service: AsyncMock, user_id: uuid.UUID,
    ) -> None:
        note_id = uuid.uuid4()
        mock_service.search.return_value = SearchResponse(results=[
            SearchResult(
                chunk_id=uuid.uuid4(),
                note_id=note_id,
                chunk_index=0,
                content="some content",
                score=0.95,
            ),
        ])

        resp = await client.post(SEARCH, json={"query": "test query"})

        assert resp.status_code == 200
        assert len(resp.json()["results"]) == 1
        assert resp.json()["results"][0]["score"] == 0.95
        mock_service.search.assert_called_once_with(user_id, "test query", 5)

    @pytest.mark.anyio()
    async def test_custom_limit(
        self, client: AsyncClient, mock_service: AsyncMock, user_id: uuid.UUID,
    ) -> None:
        mock_service.search.return_value = SearchResponse(results=[])

        resp = await client.post(SEARCH, json={"query": "test", "limit": 10})

        assert resp.status_code == 200
        mock_service.search.assert_called_once_with(user_id, "test", 10)

    @pytest.mark.anyio()
    async def test_empty_query_rejected(self, client: AsyncClient) -> None:
        resp = await client.post(SEARCH, json={"query": ""})

        assert resp.status_code == 422

    @pytest.mark.anyio()
    async def test_limit_too_high(self, client: AsyncClient) -> None:
        resp = await client.post(SEARCH, json={"query": "test", "limit": 100})

        assert resp.status_code == 422

    @pytest.mark.anyio()
    async def test_limit_zero(self, client: AsyncClient) -> None:
        resp = await client.post(SEARCH, json={"query": "test", "limit": 0})

        assert resp.status_code == 422

    @pytest.mark.anyio()
    async def test_no_results(
        self, client: AsyncClient, mock_service: AsyncMock,
    ) -> None:
        mock_service.search.return_value = SearchResponse(results=[])

        resp = await client.post(SEARCH, json={"query": "nothing"})

        assert resp.status_code == 200
        assert resp.json()["results"] == []

    @pytest.mark.anyio()
    async def test_unauthorized(self, app: FastAPI) -> None:
        app.dependency_overrides.pop(get_current_user)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.post(SEARCH, json={"query": "test"})

        assert resp.status_code == 401