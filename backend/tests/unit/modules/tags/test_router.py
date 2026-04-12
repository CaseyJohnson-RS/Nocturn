"""Unit tests for tags router."""

import uuid
from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from src.app.common.exceptions import ConflictError, NotFoundError
from src.app.middleware.auth import get_current_user
from src.app.modules.tags.router import get_tags_service, router
from src.app.modules.tags.schemas import TagListResponse, TagResponse

TAGS = "/api/tags"


def _tag_response(
    tag_id: uuid.UUID | None = None,
    user_id: uuid.UUID | None = None,
    name: str = "work",
) -> TagResponse:
    return TagResponse(
        id=tag_id or uuid.uuid4(),
        user_id=user_id or uuid.uuid4(),
        name=name,
        created_at=datetime.now(UTC),
    )


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
    test_app.dependency_overrides[get_tags_service] = lambda: mock_service
    test_app.dependency_overrides[get_current_user] = lambda: MagicMock(id=user_id, role="user")
    return test_app


@pytest.fixture()
async def client(app: FastAPI) -> AsyncGenerator[AsyncClient, None]:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


# --- POST / ---


class TestCreateTag:
    @pytest.mark.anyio()
    async def test_success(
        self,
        client: AsyncClient,
        mock_service: AsyncMock,
        user_id: uuid.UUID,
    ) -> None:
        mock_service.create.return_value = _tag_response(user_id=user_id, name="work")

        resp = await client.post(TAGS, json={"name": "work"})

        assert resp.status_code == 201
        assert resp.json()["name"] == "work"
        mock_service.create.assert_called_once_with(user_id, "work")

    @pytest.mark.anyio()
    async def test_empty_name(self, client: AsyncClient) -> None:
        resp = await client.post(TAGS, json={"name": ""})

        assert resp.status_code == 422

    @pytest.mark.anyio()
    async def test_name_too_long(self, client: AsyncClient) -> None:
        resp = await client.post(TAGS, json={"name": "a" * 51})

        assert resp.status_code == 422

    @pytest.mark.anyio()
    async def test_duplicate(self, client: AsyncClient, mock_service: AsyncMock) -> None:
        mock_service.create.side_effect = ConflictError("already exists")

        resp = await client.post(TAGS, json={"name": "work"})

        assert resp.status_code == 409

    @pytest.mark.anyio()
    async def test_limit_reached(self, client: AsyncClient, mock_service: AsyncMock) -> None:
        mock_service.create.side_effect = ConflictError("limit")

        resp = await client.post(TAGS, json={"name": "new"})

        assert resp.status_code == 409


# --- GET / ---


class TestListTags:
    @pytest.mark.anyio()
    async def test_success(self, client: AsyncClient, mock_service: AsyncMock) -> None:
        mock_service.list.return_value = TagListResponse(
            items=[_tag_response()],
            total=1,
            limit=100,
            offset=0,
        )

        resp = await client.get(TAGS)

        assert resp.status_code == 200
        assert resp.json()["total"] == 1

    @pytest.mark.anyio()
    async def test_with_search(
        self,
        client: AsyncClient,
        mock_service: AsyncMock,
        user_id: uuid.UUID,
    ) -> None:
        mock_service.list.return_value = TagListResponse(
            items=[],
            total=0,
            limit=100,
            offset=0,
        )

        resp = await client.get(TAGS, params={"search": "work"})

        assert resp.status_code == 200
        mock_service.list.assert_called_once_with(user_id, 100, 0, "work")

    @pytest.mark.anyio()
    async def test_pagination(
        self,
        client: AsyncClient,
        mock_service: AsyncMock,
        user_id: uuid.UUID,
    ) -> None:
        mock_service.list.return_value = TagListResponse(
            items=[],
            total=0,
            limit=10,
            offset=5,
        )

        resp = await client.get(TAGS, params={"limit": 10, "offset": 5})

        assert resp.status_code == 200
        mock_service.list.assert_called_once_with(user_id, 10, 5, None)

    @pytest.mark.anyio()
    async def test_limit_too_high(self, client: AsyncClient) -> None:
        resp = await client.get(TAGS, params={"limit": 200})

        assert resp.status_code == 422

    @pytest.mark.anyio()
    async def test_negative_offset(self, client: AsyncClient) -> None:
        resp = await client.get(TAGS, params={"offset": -1})

        assert resp.status_code == 422


# --- GET /{tag_id} ---


class TestGetTag:
    @pytest.mark.anyio()
    async def test_success(self, client: AsyncClient, mock_service: AsyncMock) -> None:
        tag_id = uuid.uuid4()
        mock_service.get.return_value = _tag_response(tag_id=tag_id)

        resp = await client.get(f"{TAGS}/{tag_id}")

        assert resp.status_code == 200
        assert resp.json()["id"] == str(tag_id)

    @pytest.mark.anyio()
    async def test_not_found(self, client: AsyncClient, mock_service: AsyncMock) -> None:
        mock_service.get.side_effect = NotFoundError("Tag not found")

        resp = await client.get(f"{TAGS}/{uuid.uuid4()}")

        assert resp.status_code == 404


# --- PUT /{tag_id} ---


class TestUpdateTag:
    @pytest.mark.anyio()
    async def test_success(
        self,
        client: AsyncClient,
        mock_service: AsyncMock,
        user_id: uuid.UUID,
    ) -> None:
        tag_id = uuid.uuid4()
        mock_service.update.return_value = _tag_response(tag_id=tag_id, name="updated")

        resp = await client.put(f"{TAGS}/{tag_id}", json={"name": "updated"})

        assert resp.status_code == 200
        assert resp.json()["name"] == "updated"
        mock_service.update.assert_called_once_with(user_id, tag_id, "updated")

    @pytest.mark.anyio()
    async def test_not_found(self, client: AsyncClient, mock_service: AsyncMock) -> None:
        mock_service.update.side_effect = NotFoundError("Tag not found")

        resp = await client.put(f"{TAGS}/{uuid.uuid4()}", json={"name": "new"})

        assert resp.status_code == 404

    @pytest.mark.anyio()
    async def test_name_conflict(self, client: AsyncClient, mock_service: AsyncMock) -> None:
        mock_service.update.side_effect = ConflictError("already exists")

        resp = await client.put(f"{TAGS}/{uuid.uuid4()}", json={"name": "taken"})

        assert resp.status_code == 409

    @pytest.mark.anyio()
    async def test_empty_name(self, client: AsyncClient) -> None:
        resp = await client.put(f"{TAGS}/{uuid.uuid4()}", json={"name": ""})

        assert resp.status_code == 422


# --- DELETE /{tag_id} ---


class TestDeleteTag:
    @pytest.mark.anyio()
    async def test_success(
        self,
        client: AsyncClient,
        mock_service: AsyncMock,
        user_id: uuid.UUID,
    ) -> None:
        tag_id = uuid.uuid4()

        resp = await client.delete(f"{TAGS}/{tag_id}")

        assert resp.status_code == 204
        mock_service.delete.assert_called_once_with(user_id, tag_id)

    @pytest.mark.anyio()
    async def test_not_found(self, client: AsyncClient, mock_service: AsyncMock) -> None:
        mock_service.delete.side_effect = NotFoundError("Tag not found")

        resp = await client.delete(f"{TAGS}/{uuid.uuid4()}")

        assert resp.status_code == 404


# --- Auth ---


class TestUnauthorized:
    @pytest.mark.anyio()
    async def test_all_endpoints_require_auth(self, app: FastAPI) -> None:
        app.dependency_overrides.pop(get_current_user)
        tag_id = uuid.uuid4()

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            for method, url in [
                ("POST", TAGS),
                ("GET", TAGS),
                ("GET", f"{TAGS}/{tag_id}"),
                ("PUT", f"{TAGS}/{tag_id}"),
                ("DELETE", f"{TAGS}/{tag_id}"),
            ]:
                resp = await ac.request(method, url)
                assert resp.status_code == 401, f"{method} {url} should be 401"
