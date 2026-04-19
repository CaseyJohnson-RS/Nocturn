"""Unit tests for notes router."""


import uuid
from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from src.app.common.exceptions import ConflictError, NotFoundError
from src.app.middleware.auth import get_current_user
from src.app.modules.notes.router import get_notes_service, router
from src.app.modules.notes.schemas import (
    BatchNotesResponse,
    NoteListItem,
    NoteListResponse,
    NoteResponse,
    NoteSearchResponse,
    TagBrief,
)

NOTES = "/api/notes"


def _note_response(
    note_id: uuid.UUID | None = None,
    user_id: uuid.UUID | None = None,
    title: str | None = "Test Note",
    content: str | None = "Some content",
    version: int = 1,
    deleted_at: datetime | None = None,
    tags: list[TagBrief] | None = None,
) -> NoteResponse:
    return NoteResponse(
        id=note_id or uuid.uuid4(),
        user_id=user_id or uuid.uuid4(),
        title=title,
        content=content,
        version=version,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
        deleted_at=deleted_at,
        tags=tags or [],
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
    test_app.dependency_overrides[get_notes_service] = lambda: mock_service
    test_app.dependency_overrides[get_current_user] = lambda: MagicMock(id=user_id, role="user")
    return test_app


@pytest.fixture()
async def client(app: FastAPI) -> AsyncGenerator[AsyncClient, None]:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac



# --- POST / ---


class TestCreateNote:
    @pytest.mark.anyio()
    async def test_success(
        self,
        client: AsyncClient,
        mock_service: AsyncMock,
        user_id: uuid.UUID,
    ) -> None:
        mock_service.create.return_value = _note_response(user_id=user_id, title="New")

        resp = await client.post(
            NOTES,
            json={
                "title": "New",
                "content": "Body",
                "tag_ids": [],
            },
        )

        assert resp.status_code == 201
        assert resp.json()["title"] == "New"
        mock_service.create.assert_called_once_with(user_id, "New", "Body", [])

    @pytest.mark.anyio()
    async def test_title_too_long(self, client: AsyncClient) -> None:
        resp = await client.post(
            NOTES,
            json={
                "title": "a" * 201,
                "content": "Body",
                "tag_ids": [],
            },
        )

        assert resp.status_code == 422

    @pytest.mark.anyio()
    async def test_note_limit_reached(
        self,
        client: AsyncClient,
        mock_service: AsyncMock,
    ) -> None:
        mock_service.create.side_effect = ConflictError("Note limit reached")

        resp = await client.post(
            NOTES,
            json={
                "title": "New",
                "content": "Body",
                "tag_ids": [],
            },
        )

        assert resp.status_code == 409


# --- GET / ---


class TestListNotes:
    @pytest.mark.anyio()
    async def test_success(self, client: AsyncClient, mock_service: AsyncMock) -> None:
        mock_service.list.return_value = NoteListResponse(
            items=[
                NoteListItem(
                    id=uuid.uuid4(),
                    title="Note",
                    updated_at=datetime.now(UTC),
                    deleted_at=None,
                )
            ],
            total=1,
            limit=50,
            offset=0,
        )

        resp = await client.get(NOTES)

        assert resp.status_code == 200
        assert resp.json()["total"] == 1

    @pytest.mark.anyio()
    async def test_with_filters(
        self,
        client: AsyncClient,
        mock_service: AsyncMock,
        user_id: uuid.UUID,
    ) -> None:
        mock_service.list.return_value = NoteListResponse(
            items=[],
            total=0,
            limit=10,
            offset=5,
        )

        tag_id = uuid.uuid4()
        resp = await client.get(
            NOTES,
            params={
                "limit": 10,
                "offset": 5,
                "deleted": True,
                "search": "test",
                "tag_ids": str(tag_id),
            },
        )

        assert resp.status_code == 200
        mock_service.list.assert_called_once_with(user_id, 10, 5, True, "test", [tag_id])

    @pytest.mark.anyio()
    async def test_limit_too_high(self, client: AsyncClient) -> None:
        resp = await client.get(NOTES, params={"limit": 300})

        assert resp.status_code == 422

    @pytest.mark.anyio()
    async def test_negative_offset(self, client: AsyncClient) -> None:
        resp = await client.get(NOTES, params={"offset": -1})

        assert resp.status_code == 422


# --- GET /{note_id} ---


class TestGetNote:
    @pytest.mark.anyio()
    async def test_success(
        self,
        client: AsyncClient,
        mock_service: AsyncMock,
        user_id: uuid.UUID,
    ) -> None:
        note_id = uuid.uuid4()
        mock_service.get.return_value = _note_response(note_id=note_id, user_id=user_id)

        resp = await client.get(f"{NOTES}/{note_id}")

        assert resp.status_code == 200
        assert resp.json()["id"] == str(note_id)

    @pytest.mark.anyio()
    async def test_not_found(self, client: AsyncClient, mock_service: AsyncMock) -> None:
        mock_service.get.side_effect = NotFoundError("Note not found")

        resp = await client.get(f"{NOTES}/{uuid.uuid4()}")

        assert resp.status_code == 404


# --- PUT /{note_id} ---


class TestUpdateNote:
    @pytest.mark.anyio()
    async def test_update_title(
        self,
        client: AsyncClient,
        mock_service: AsyncMock,
        user_id: uuid.UUID,
    ) -> None:
        note_id = uuid.uuid4()
        mock_service.update.return_value = _note_response(note_id=note_id, title="Updated")

        resp = await client.put(
            f"{NOTES}/{note_id}",
            json={
                "title": "Updated",
                "version": 1,
            },
        )

        assert resp.status_code == 200
        assert resp.json()["title"] == "Updated"
        mock_service.update.assert_called_once_with(user_id, note_id, version=1, title="Updated")

    @pytest.mark.anyio()
    async def test_update_content_only(
        self,
        client: AsyncClient,
        mock_service: AsyncMock,
        user_id: uuid.UUID,
    ) -> None:
        note_id = uuid.uuid4()
        mock_service.update.return_value = _note_response(note_id=note_id)

        resp = await client.put(
            f"{NOTES}/{note_id}",
            json={
                "content": "New body",
                "version": 1,
            },
        )

        assert resp.status_code == 200
        mock_service.update.assert_called_once_with(user_id, note_id, version=1, content="New body")

    @pytest.mark.anyio()
    async def test_version_conflict(
        self,
        client: AsyncClient,
        mock_service: AsyncMock,
    ) -> None:
        mock_service.update.side_effect = ConflictError("Version conflict")

        resp = await client.put(
            f"{NOTES}/{uuid.uuid4()}",
            json={
                "title": "New",
                "version": 1,
            },
        )

        assert resp.status_code == 409

    @pytest.mark.anyio()
    async def test_version_required(self, client: AsyncClient) -> None:
        resp = await client.put(f"{NOTES}/{uuid.uuid4()}", json={"title": "New"})

        assert resp.status_code == 422

    @pytest.mark.anyio()
    async def test_version_must_be_positive(self, client: AsyncClient) -> None:
        resp = await client.put(
            f"{NOTES}/{uuid.uuid4()}",
            json={
                "title": "New",
                "version": 0,
            },
        )

        assert resp.status_code == 422


# --- DELETE /{note_id} ---


class TestDeleteNote:
    @pytest.mark.anyio()
    async def test_soft_delete(
        self,
        client: AsyncClient,
        mock_service: AsyncMock,
        user_id: uuid.UUID,
    ) -> None:
        note_id = uuid.uuid4()

        resp = await client.delete(f"{NOTES}/{note_id}")

        assert resp.status_code == 204
        mock_service.soft_delete.assert_called_once_with(user_id, note_id)
        mock_service.hard_delete.assert_not_called()

    @pytest.mark.anyio()
    async def test_hard_delete(
        self,
        client: AsyncClient,
        mock_service: AsyncMock,
        user_id: uuid.UUID,
    ) -> None:
        note_id = uuid.uuid4()

        resp = await client.delete(f"{NOTES}/{note_id}", params={"permanent": True})

        assert resp.status_code == 204
        mock_service.hard_delete.assert_called_once_with(user_id, note_id)
        mock_service.soft_delete.assert_not_called()

    @pytest.mark.anyio()
    async def test_not_found(self, client: AsyncClient, mock_service: AsyncMock) -> None:
        mock_service.soft_delete.side_effect = NotFoundError("Note not found")

        resp = await client.delete(f"{NOTES}/{uuid.uuid4()}")

        assert resp.status_code == 404


# --- POST /{note_id}/restore ---


class TestRestoreNote:
    @pytest.mark.anyio()
    async def test_success(
        self,
        client: AsyncClient,
        mock_service: AsyncMock,
        user_id: uuid.UUID,
    ) -> None:
        note_id = uuid.uuid4()
        mock_service.restore.return_value = _note_response(note_id=note_id, deleted_at=None)

        resp = await client.post(f"{NOTES}/{note_id}/restore")

        assert resp.status_code == 200
        assert resp.json()["deleted_at"] is None

    @pytest.mark.anyio()
    async def test_not_found(self, client: AsyncClient, mock_service: AsyncMock) -> None:
        mock_service.restore.side_effect = NotFoundError("Note not found")

        resp = await client.post(f"{NOTES}/{uuid.uuid4()}/restore")

        assert resp.status_code == 404


# --- PUT /{note_id}/tags ---


class TestUpdateNoteTags:
    @pytest.mark.anyio()
    async def test_success(
        self,
        client: AsyncClient,
        mock_service: AsyncMock,
        user_id: uuid.UUID,
    ) -> None:
        note_id = uuid.uuid4()
        tag_id = uuid.uuid4()
        mock_service.update_tags.return_value = _note_response(
            note_id=note_id,
            tags=[TagBrief(id=tag_id, name="work")],
        )

        resp = await client.put(f"{NOTES}/{note_id}/tags", json={"tag_ids": [str(tag_id)]})

        assert resp.status_code == 200
        assert len(resp.json()["tags"]) == 1
        mock_service.update_tags.assert_called_once_with(user_id, note_id, [tag_id])

    @pytest.mark.anyio()
    async def test_clear_tags(
        self,
        client: AsyncClient,
        mock_service: AsyncMock,
    ) -> None:
        note_id = uuid.uuid4()
        mock_service.update_tags.return_value = _note_response(note_id=note_id, tags=[])

        resp = await client.put(f"{NOTES}/{note_id}/tags", json={"tag_ids": []})

        assert resp.status_code == 200
        assert resp.json()["tags"] == []


# --- POST /batch ---


class TestBatchGetNotes:
    @pytest.mark.anyio()
    async def test_success(
        self,
        client: AsyncClient,
        mock_service: AsyncMock,
        user_id: uuid.UUID,
    ) -> None:
        ids = [uuid.uuid4(), uuid.uuid4()]
        mock_service.batch_get.return_value = BatchNotesResponse(
            items=[_note_response(note_id=ids[0]), _note_response(note_id=ids[1])],
        )

        resp = await client.post(f"{NOTES}/batch", json={"note_ids": [str(i) for i in ids]})

        assert resp.status_code == 200
        assert len(resp.json()["items"]) == 2
        mock_service.batch_get.assert_called_once_with(user_id, ids)

    @pytest.mark.anyio()
    async def test_empty(self, client: AsyncClient, mock_service: AsyncMock) -> None:
        mock_service.batch_get.return_value = BatchNotesResponse(items=[])

        resp = await client.post(f"{NOTES}/batch", json={"note_ids": []})

        assert resp.status_code == 200
        assert resp.json()["items"] == []


# --- GET /search ---


class TestSearchNotes:
    @pytest.mark.anyio()
    async def test_success(
        self,
        client: AsyncClient,
        mock_service: AsyncMock,
        user_id: uuid.UUID,
    ) -> None:
        mock_service.search_keywords.return_value = NoteSearchResponse(
            items=[
                NoteListItem(
                    id=uuid.uuid4(),
                    title="Python Guide",
                    updated_at=datetime.now(UTC),
                    deleted_at=None,
                )
            ],
            total=1,
            limit=50,
            keywords=["python"],
        )

        resp = await client.get(f"{NOTES}/search", params={"keywords": "python"})

        assert resp.status_code == 200
        assert resp.json()["total"] == 1
        assert resp.json()["keywords"] == ["python"]
        mock_service.search_keywords.assert_called_once_with(user_id, ["python"], 50)

    @pytest.mark.anyio()
    async def test_multiple_keywords_parsed(
        self,
        client: AsyncClient,
        mock_service: AsyncMock,
        user_id: uuid.UUID,
    ) -> None:
        mock_service.search_keywords.return_value = NoteSearchResponse(
            items=[], total=0, limit=50, keywords=["python", "async"]
        )

        resp = await client.get(f"{NOTES}/search", params={"keywords": "python,async"})

        assert resp.status_code == 200
        mock_service.search_keywords.assert_called_once_with(user_id, ["python", "async"], 50)

    @pytest.mark.anyio()
    async def test_keywords_whitespace_stripped(
        self,
        client: AsyncClient,
        mock_service: AsyncMock,
        user_id: uuid.UUID,
    ) -> None:
        mock_service.search_keywords.return_value = NoteSearchResponse(
            items=[], total=0, limit=50, keywords=["python", "async"]
        )

        resp = await client.get(f"{NOTES}/search", params={"keywords": " python , async "})

        assert resp.status_code == 200
        mock_service.search_keywords.assert_called_once_with(user_id, ["python", "async"], 50)

    @pytest.mark.anyio()
    async def test_custom_limit(
        self,
        client: AsyncClient,
        mock_service: AsyncMock,
        user_id: uuid.UUID,
    ) -> None:
        mock_service.search_keywords.return_value = NoteSearchResponse(
            items=[], total=0, limit=10, keywords=["test"]
        )

        resp = await client.get(f"{NOTES}/search", params={"keywords": "test", "limit": 10})

        assert resp.status_code == 200
        mock_service.search_keywords.assert_called_once_with(user_id, ["test"], 10)

    @pytest.mark.anyio()
    async def test_limit_too_high(self, client: AsyncClient) -> None:
        resp = await client.get(f"{NOTES}/search", params={"keywords": "test", "limit": 300})

        assert resp.status_code == 422

    @pytest.mark.anyio()
    async def test_limit_too_low(self, client: AsyncClient) -> None:
        resp = await client.get(f"{NOTES}/search", params={"keywords": "test", "limit": 0})

        assert resp.status_code == 422

    @pytest.mark.anyio()
    async def test_keywords_missing(self, client: AsyncClient) -> None:
        resp = await client.get(f"{NOTES}/search")

        assert resp.status_code == 422


# --- Auth ---


class TestUnauthorized:
    @pytest.mark.anyio()
    async def test_all_endpoints_require_auth(self, app: FastAPI) -> None:
        app.dependency_overrides.pop(get_current_user)
        note_id = uuid.uuid4()

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            for method, url in [
                ("POST", NOTES),
                ("GET", NOTES),
                ("GET", f"{NOTES}/search?keywords=test"),
                ("GET", f"{NOTES}/{note_id}"),
                ("PUT", f"{NOTES}/{note_id}"),
                ("DELETE", f"{NOTES}/{note_id}"),
                ("POST", f"{NOTES}/{note_id}/restore"),
                ("PUT", f"{NOTES}/{note_id}/tags"),
                ("POST", f"{NOTES}/batch"),
            ]:
                resp = await ac.request(method, url)
                assert resp.status_code == 401, f"{method} {url} should be 401"
