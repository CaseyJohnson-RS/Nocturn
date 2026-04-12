"""Unit tests for AI router."""

import uuid
from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from src.app.middleware.auth import get_current_user
from src.app.modules.ai.router import router
from src.app.modules.ai.schemas import (
    MessageResponse,
    MessagesListResponse,
    SessionListResponse,
    SessionResponse,
)

BASE = "/api/ai"


def _session_response(
    session_id: uuid.UUID | None = None,
    user_id: uuid.UUID | None = None,
    title: str | None = None,
) -> SessionResponse:
    return SessionResponse(
        id=session_id or uuid.uuid4(),
        user_id=user_id or uuid.uuid4(),
        title=title,
        created_at=datetime.now(UTC),
        last_message_at=None,
    )


def _message_response(
    message_id: uuid.UUID | None = None,
    session_id: uuid.UUID | None = None,
) -> MessageResponse:
    return MessageResponse(
        id=message_id or uuid.uuid4(),
        session_id=session_id or uuid.uuid4(),
        role="assistant",
        content="Hello",
        actions=None,
        attached_note_ids=None,
        created_at=datetime.now(UTC),
    )


# --- Fixtures ---


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
    test_app.dependency_overrides[get_current_user] = lambda: MagicMock(
        id=user_id, role="user",
    )

    # Patch AIService so that any instantiation returns our mock
    patcher = patch(
        "src.app.modules.ai.router.AIService", return_value=mock_service,
    )
    patcher.start()
    test_app._ai_patcher = patcher  # type: ignore[attr-defined]
    return test_app


@pytest.fixture()
async def client(app: FastAPI) -> AsyncGenerator[AsyncClient, None]:
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test",
    ) as ac:
        yield ac
    app._ai_patcher.stop()  # type: ignore[attr-defined]


# =====================================================================
# POST /sessions
# =====================================================================


class TestCreateSession:
    @pytest.mark.anyio()
    async def test_success(
        self,
        client: AsyncClient,
        mock_service: AsyncMock,
        user_id: uuid.UUID,
    ) -> None:
        mock_service.create_session.return_value = _session_response(
            user_id=user_id,
        )

        resp = await client.post(f"{BASE}/sessions", json={})

        assert resp.status_code == 201
        mock_service.create_session.assert_called_once_with(user_id, None)

    @pytest.mark.anyio()
    async def test_with_dismiss_session_id(
        self,
        client: AsyncClient,
        mock_service: AsyncMock,
        user_id: uuid.UUID,
    ) -> None:
        old_id = uuid.uuid4()
        mock_service.create_session.return_value = _session_response(
            user_id=user_id,
        )

        resp = await client.post(
            f"{BASE}/sessions",
            json={"dismiss_session_id": str(old_id)},
        )

        assert resp.status_code == 201
        mock_service.create_session.assert_called_once_with(user_id, old_id)


# =====================================================================
# GET /sessions
# =====================================================================


class TestListSessions:
    @pytest.mark.anyio()
    async def test_success(
        self, client: AsyncClient, mock_service: AsyncMock,
    ) -> None:
        mock_service.list_sessions.return_value = SessionListResponse(
            items=[_session_response()], total=1,
        )

        resp = await client.get(f"{BASE}/sessions")

        assert resp.status_code == 200
        assert resp.json()["total"] == 1

    @pytest.mark.anyio()
    async def test_pagination_params(
        self,
        client: AsyncClient,
        mock_service: AsyncMock,
        user_id: uuid.UUID,
    ) -> None:
        mock_service.list_sessions.return_value = SessionListResponse(
            items=[], total=0,
        )

        resp = await client.get(
            f"{BASE}/sessions", params={"limit": 10, "offset": 5},
        )

        assert resp.status_code == 200
        mock_service.list_sessions.assert_called_once_with(user_id, 10, 5)

    @pytest.mark.anyio()
    async def test_limit_too_high(self, client: AsyncClient) -> None:
        resp = await client.get(
            f"{BASE}/sessions", params={"limit": 200},
        )
        assert resp.status_code == 422

    @pytest.mark.anyio()
    async def test_negative_offset(self, client: AsyncClient) -> None:
        resp = await client.get(
            f"{BASE}/sessions", params={"offset": -1},
        )
        assert resp.status_code == 422


# =====================================================================
# DELETE /sessions/{session_id}
# =====================================================================


class TestDeleteSession:
    @pytest.mark.anyio()
    async def test_success(
        self,
        client: AsyncClient,
        mock_service: AsyncMock,
        user_id: uuid.UUID,
    ) -> None:
        sid = uuid.uuid4()

        resp = await client.delete(f"{BASE}/sessions/{sid}")

        assert resp.status_code == 204
        mock_service.delete_session.assert_called_once_with(user_id, sid)


# =====================================================================
# PUT /sessions/{session_id}
# =====================================================================


class TestUpdateSession:
    @pytest.mark.anyio()
    async def test_success(
        self,
        client: AsyncClient,
        mock_service: AsyncMock,
        user_id: uuid.UUID,
    ) -> None:
        sid = uuid.uuid4()
        mock_service.update_session.return_value = _session_response(
            session_id=sid, title="New Title",
        )

        resp = await client.put(
            f"{BASE}/sessions/{sid}",
            json={"title": "New Title"},
        )

        assert resp.status_code == 200
        assert resp.json()["title"] == "New Title"
        mock_service.update_session.assert_called_once_with(
            user_id, sid, "New Title",
        )

    @pytest.mark.anyio()
    async def test_title_too_long(self, client: AsyncClient) -> None:
        sid = uuid.uuid4()
        resp = await client.put(
            f"{BASE}/sessions/{sid}",
            json={"title": "x" * 201},
        )
        assert resp.status_code == 422

    @pytest.mark.anyio()
    async def test_empty_title(self, client: AsyncClient) -> None:
        sid = uuid.uuid4()
        resp = await client.put(
            f"{BASE}/sessions/{sid}",
            json={"title": ""},
        )
        assert resp.status_code == 422


# =====================================================================
# GET /sessions/{session_id}/messages
# =====================================================================


class TestGetMessages:
    @pytest.mark.anyio()
    async def test_success(
        self, client: AsyncClient, mock_service: AsyncMock,
    ) -> None:
        sid = uuid.uuid4()
        mock_service.get_messages.return_value = MessagesListResponse(
            items=[_message_response(session_id=sid)], total=1,
        )

        resp = await client.get(f"{BASE}/sessions/{sid}/messages")

        assert resp.status_code == 200
        assert resp.json()["total"] == 1

    @pytest.mark.anyio()
    async def test_pagination(
        self,
        client: AsyncClient,
        mock_service: AsyncMock,
        user_id: uuid.UUID,
    ) -> None:
        sid = uuid.uuid4()
        mock_service.get_messages.return_value = MessagesListResponse(
            items=[], total=0,
        )

        resp = await client.get(
            f"{BASE}/sessions/{sid}/messages",
            params={"limit": 100, "offset": 20},
        )

        assert resp.status_code == 200
        mock_service.get_messages.assert_called_once_with(
            user_id, sid, 100, 20,
        )

    @pytest.mark.anyio()
    async def test_limit_too_high(self, client: AsyncClient) -> None:
        resp = await client.get(
            f"{BASE}/sessions/{uuid.uuid4()}/messages",
            params={"limit": 300},
        )
        assert resp.status_code == 422


# =====================================================================
# POST /sessions/{session_id}/messages (SSE — validate pre-stream)
# =====================================================================


class TestSendMessage:
    @pytest.mark.anyio()
    async def test_pre_validation_error_returns_json(
        self, client: AsyncClient, mock_service: AsyncMock,
    ) -> None:
        mock_service.pre_validate_send.return_value = (404, "Session not found")

        resp = await client.post(
            f"{BASE}/sessions/{uuid.uuid4()}/messages",
            json={"content": "Hello"},
        )

        assert resp.status_code == 404
        assert resp.json()["detail"] == "Session not found"

    @pytest.mark.anyio()
    async def test_validation_passes_starts_stream(
        self, client: AsyncClient, mock_service: AsyncMock,
    ) -> None:
        mock_service.pre_validate_send.return_value = None

        async def fake_stream(*a, **kw):
            yield 'event: ai:done\ndata: {}\n\n'

        mock_service.send_message = MagicMock(return_value=fake_stream())

        resp = await client.post(
            f"{BASE}/sessions/{uuid.uuid4()}/messages",
            json={"content": "Hello"},
        )

        assert resp.status_code == 200
        assert resp.headers["content-type"] == "text/event-stream; charset=utf-8"

    @pytest.mark.anyio()
    async def test_content_too_long(self, client: AsyncClient) -> None:
        resp = await client.post(
            f"{BASE}/sessions/{uuid.uuid4()}/messages",
            json={"content": "x" * 4001},
        )
        assert resp.status_code == 422

    @pytest.mark.anyio()
    async def test_empty_content(self, client: AsyncClient) -> None:
        resp = await client.post(
            f"{BASE}/sessions/{uuid.uuid4()}/messages",
            json={"content": ""},
        )
        assert resp.status_code == 422

    @pytest.mark.anyio()
    async def test_attached_note_ids_passed(
        self,
        client: AsyncClient,
        mock_service: AsyncMock,
        user_id: uuid.UUID,
    ) -> None:
        mock_service.pre_validate_send.return_value = None
        nid = uuid.uuid4()

        async def fake_stream(*a, **kw):
            yield 'event: ai:done\ndata: {}\n\n'

        mock_service.send_message = MagicMock(return_value=fake_stream())

        sid = uuid.uuid4()
        resp = await client.post(
            f"{BASE}/sessions/{sid}/messages",
            json={"content": "Hello", "attached_note_ids": [str(nid)]},
        )

        assert resp.status_code == 200
        mock_service.send_message.assert_called_once_with(
            user_id, sid, "Hello", [nid],
        )


# =====================================================================
# POST /sessions/{session_id}/cancel
# =====================================================================


class TestCancelGeneration:
    @pytest.mark.anyio()
    async def test_success(
        self,
        client: AsyncClient,
        mock_service: AsyncMock,
        user_id: uuid.UUID,
    ) -> None:
        sid = uuid.uuid4()
        mock_service.cancel_generation.return_value = {"status": "cancelled"}

        resp = await client.post(f"{BASE}/sessions/{sid}/cancel")

        assert resp.status_code == 200
        assert resp.json()["status"] == "cancelled"


# =====================================================================
# PATCH /sessions/{sid}/messages/{mid}/actions/{aid}
# =====================================================================


class TestUpdateAction:
    @pytest.mark.anyio()
    async def test_apply(
        self, client: AsyncClient, mock_service: AsyncMock,
    ) -> None:
        sid, mid, aid = uuid.uuid4(), uuid.uuid4(), str(uuid.uuid4())
        mock_service.update_action_status.return_value = _message_response(
            message_id=mid, session_id=sid,
        )

        resp = await client.patch(
            f"{BASE}/sessions/{sid}/messages/{mid}/actions/{aid}",
            json={"status": "applied"},
        )

        assert resp.status_code == 200

    @pytest.mark.anyio()
    async def test_dismiss(
        self, client: AsyncClient, mock_service: AsyncMock,
    ) -> None:
        sid, mid, aid = uuid.uuid4(), uuid.uuid4(), str(uuid.uuid4())
        mock_service.update_action_status.return_value = _message_response()

        resp = await client.patch(
            f"{BASE}/sessions/{sid}/messages/{mid}/actions/{aid}",
            json={"status": "dismissed"},
        )

        assert resp.status_code == 200

    @pytest.mark.anyio()
    async def test_invalid_status(self, client: AsyncClient) -> None:
        resp = await client.patch(
            f"{BASE}/sessions/{uuid.uuid4()}/messages/{uuid.uuid4()}/actions/x",
            json={"status": "invalid"},
        )
        assert resp.status_code == 422


# =====================================================================
# POST /sessions/{sid}/confirm/{cid}
# =====================================================================


class TestConfirmBulk:
    @pytest.mark.anyio()
    async def test_pre_validation_error(
        self, client: AsyncClient, mock_service: AsyncMock,
    ) -> None:
        mock_service.pre_validate_confirm.return_value = (
            404, "Confirmation not found",
        )

        resp = await client.post(
            f"{BASE}/sessions/{uuid.uuid4()}/confirm/some-id",
        )

        assert resp.status_code == 404
        assert resp.json()["detail"] == "Confirmation not found"

    @pytest.mark.anyio()
    async def test_validation_passes_streams(
        self, client: AsyncClient, mock_service: AsyncMock,
    ) -> None:
        mock_service.pre_validate_confirm.return_value = None

        async def fake_stream(*a, **kw):
            yield 'event: ai:done\ndata: {}\n\n'

        mock_service.confirm_bulk = MagicMock(return_value=fake_stream())

        resp = await client.post(
            f"{BASE}/sessions/{uuid.uuid4()}/confirm/some-id",
        )

        assert resp.status_code == 200
        assert resp.headers["content-type"] == "text/event-stream; charset=utf-8"


# =====================================================================
# POST /sessions/{sid}/dismiss/{cid}
# =====================================================================


class TestDismissBulk:
    @pytest.mark.anyio()
    async def test_success(
        self, client: AsyncClient, mock_service: AsyncMock,
    ) -> None:
        sid = uuid.uuid4()
        mock_service.dismiss_bulk.return_value = _message_response(session_id=sid)

        resp = await client.post(
            f"{BASE}/sessions/{sid}/dismiss/some-id",
        )

        assert resp.status_code == 200
