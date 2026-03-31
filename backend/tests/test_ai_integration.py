"""Integration tests for the AI assistant module."""

import json
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.ai.models import ChatMessage, ChatSession
from app.modules.auth.models import User


# --- Helpers ---

async def register_and_login(client: AsyncClient, db: AsyncSession, email="ai@test.com") -> str:
    await client.post("/api/auth/register", json={
        "email": email,
        "password": "ValidPass1",
        "nickname": email.split("@")[0],
    })
    await db.execute(update(User).where(User.email == email).values(is_email_confirmed=True))
    await db.commit()
    resp = await client.post("/api/auth/login", json={
        "email": email,
        "password": "ValidPass1",
    })
    return resp.json()["access_token"]


def auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def create_session(client: AsyncClient, token: str, title=None) -> dict:
    resp = await client.post("/api/ai/sessions", json={"title": title}, headers=auth(token))
    return resp.json()


# --- Sessions ---

class TestCreateSession:
    async def test_create_session(self, client: AsyncClient, db: AsyncSession):
        token = await register_and_login(client, db)
        resp = await client.post("/api/ai/sessions", json={"title": "Test Chat"}, headers=auth(token))
        assert resp.status_code == 201
        data = resp.json()
        assert data["title"] == "Test Chat"
        assert "id" in data

    async def test_create_session_no_title(self, client: AsyncClient, db: AsyncSession):
        token = await register_and_login(client, db)
        resp = await client.post("/api/ai/sessions", json={}, headers=auth(token))
        assert resp.status_code == 201
        assert resp.json()["title"] is None

    async def test_create_session_unauthenticated(self, client: AsyncClient):
        resp = await client.post("/api/ai/sessions", json={})
        assert resp.status_code == 401


class TestListSessions:
    async def test_list_sessions(self, client: AsyncClient, db: AsyncSession):
        token = await register_and_login(client, db)
        await create_session(client, token, "Chat 1")
        await create_session(client, token, "Chat 2")

        resp = await client.get("/api/ai/sessions", headers=auth(token))
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2
        assert len(data["items"]) == 2

    async def test_list_sessions_isolation(self, client: AsyncClient, db: AsyncSession):
        token1 = await register_and_login(client, db, "user1@test.com")
        token2 = await register_and_login(client, db, "user2@test.com")
        await create_session(client, token1, "User1 Chat")

        resp = await client.get("/api/ai/sessions", headers=auth(token2))
        assert resp.json()["total"] == 0


class TestGetSession:
    async def test_get_session(self, client: AsyncClient, db: AsyncSession):
        token = await register_and_login(client, db)
        session = await create_session(client, token, "My Chat")

        resp = await client.get(f"/api/ai/sessions/{session['id']}", headers=auth(token))
        assert resp.status_code == 200
        data = resp.json()
        assert data["title"] == "My Chat"
        assert data["messages"] == []

    async def test_get_session_not_found(self, client: AsyncClient, db: AsyncSession):
        token = await register_and_login(client, db)
        resp = await client.get(
            "/api/ai/sessions/00000000-0000-0000-0000-000000000000",
            headers=auth(token),
        )
        assert resp.status_code == 404

    async def test_get_session_other_user(self, client: AsyncClient, db: AsyncSession):
        token1 = await register_and_login(client, db, "user1@test.com")
        token2 = await register_and_login(client, db, "user2@test.com")
        session = await create_session(client, token1, "Private")

        resp = await client.get(f"/api/ai/sessions/{session['id']}", headers=auth(token2))
        assert resp.status_code == 404


class TestUpdateSession:
    async def test_rename_session(self, client: AsyncClient, db: AsyncSession):
        token = await register_and_login(client, db)
        session = await create_session(client, token, "Old Title")

        resp = await client.put(
            f"/api/ai/sessions/{session['id']}",
            json={"title": "New Title"},
            headers=auth(token),
        )
        assert resp.status_code == 200
        assert resp.json()["title"] == "New Title"


class TestDeleteSession:
    async def test_delete_session(self, client: AsyncClient, db: AsyncSession):
        token = await register_and_login(client, db)
        session = await create_session(client, token, "To Delete")

        resp = await client.delete(f"/api/ai/sessions/{session['id']}", headers=auth(token))
        assert resp.status_code == 204

        resp = await client.get("/api/ai/sessions", headers=auth(token))
        assert resp.json()["total"] == 0

    async def test_delete_session_not_found(self, client: AsyncClient, db: AsyncSession):
        token = await register_and_login(client, db)
        resp = await client.delete(
            "/api/ai/sessions/00000000-0000-0000-0000-000000000000",
            headers=auth(token),
        )
        assert resp.status_code == 404


# --- Chat / Send Message ---

def _mock_stream(*args, **kwargs):
    """Mock chat_completion_stream to yield known deltas."""
    async def _gen():
        yield "Hello"
        yield " from"
        yield " AI"
    return _gen()


class TestSendMessage:
    @patch("app.modules.ai.service.chat_completion_stream", side_effect=_mock_stream)
    @patch("app.modules.rag.service.create_embeddings", new_callable=AsyncMock)
    async def test_send_message_streams_response(
        self, mock_embed, mock_chat, client: AsyncClient, db: AsyncSession,
    ):
        mock_embed.return_value = [[0.1] * 2560]
        token = await register_and_login(client, db)
        session = await create_session(client, token)

        resp = await client.post(
            f"/api/ai/sessions/{session['id']}/messages",
            json={"message": "Hello AI"},
            headers=auth(token),
        )
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/event-stream")

        # Parse SSE events
        events = []
        for line in resp.text.strip().split("\n"):
            line = line.strip()
            if line.startswith("data: "):
                events.append(json.loads(line.removeprefix("data: ")))

        # Should have delta events + final done event
        deltas = [e for e in events if "delta" in e]
        done_events = [e for e in events if "done" in e]

        assert len(deltas) >= 1
        assert len(done_events) == 1
        assert done_events[0]["done"] is True
        assert done_events[0]["message"]["role"] == "assistant"
        assert "Hello" in done_events[0]["message"]["content"]

    @patch("app.modules.ai.service.chat_completion_stream", side_effect=_mock_stream)
    @patch("app.modules.rag.service.create_embeddings", new_callable=AsyncMock)
    async def test_send_message_saves_messages(
        self, mock_embed, mock_chat, client: AsyncClient, db: AsyncSession,
    ):
        mock_embed.return_value = [[0.1] * 2560]
        token = await register_and_login(client, db)
        session = await create_session(client, token)

        # Send a message (consume the stream)
        await client.post(
            f"/api/ai/sessions/{session['id']}/messages",
            json={"message": "Hello AI"},
            headers=auth(token),
        )

        # Verify messages were saved
        result = await db.execute(
            select(ChatMessage).where(ChatMessage.session_id == session["id"])
            .order_by(ChatMessage.created_at)
        )
        messages = result.scalars().all()
        assert len(messages) == 2
        assert messages[0].role == "user"
        assert messages[0].content == "Hello AI"
        assert messages[1].role == "assistant"
        assert "Hello from AI" in messages[1].content

    @patch("app.modules.ai.service.chat_completion_stream", side_effect=_mock_stream)
    @patch("app.modules.rag.service.create_embeddings", new_callable=AsyncMock)
    async def test_send_message_auto_titles_session(
        self, mock_embed, mock_chat, client: AsyncClient, db: AsyncSession,
    ):
        mock_embed.return_value = [[0.1] * 2560]
        token = await register_and_login(client, db)
        session = await create_session(client, token)  # no title

        await client.post(
            f"/api/ai/sessions/{session['id']}/messages",
            json={"message": "How do I learn Python?"},
            headers=auth(token),
        )

        # Session should be auto-titled from first user message
        resp = await client.get(f"/api/ai/sessions/{session['id']}", headers=auth(token))
        assert resp.json()["title"] == "How do I learn Python?"

    async def test_send_message_unauthenticated(self, client: AsyncClient):
        resp = await client.post(
            "/api/ai/sessions/00000000-0000-0000-0000-000000000000/messages",
            json={"message": "test"},
        )
        assert resp.status_code == 401

    async def test_send_message_empty(self, client: AsyncClient, db: AsyncSession):
        token = await register_and_login(client, db)
        session = await create_session(client, token)

        resp = await client.post(
            f"/api/ai/sessions/{session['id']}/messages",
            json={"message": ""},
            headers=auth(token),
        )
        assert resp.status_code == 422

    @patch("app.modules.ai.service.chat_completion_stream", side_effect=_mock_stream)
    @patch("app.modules.rag.service.create_embeddings", new_callable=AsyncMock)
    async def test_send_message_with_attached_notes(
        self, mock_embed, mock_chat, client: AsyncClient, db: AsyncSession,
    ):
        mock_embed.side_effect = lambda texts: [[0.1] * 2560 for _ in texts]
        token = await register_and_login(client, db)

        # Create a note
        note_resp = await client.post("/api/notes", json={
            "title": "Python Tips",
            "content": "Use list comprehensions for cleaner code.",
        }, headers=auth(token))
        note_id = note_resp.json()["id"]

        session = await create_session(client, token)

        resp = await client.post(
            f"/api/ai/sessions/{session['id']}/messages",
            json={"message": "Summarize my Python tips", "note_ids": [note_id]},
            headers=auth(token),
        )
        assert resp.status_code == 200

        # Verify assistant message has sources
        result = await db.execute(
            select(ChatMessage).where(
                ChatMessage.session_id == session["id"],
                ChatMessage.role == "assistant",
            )
        )
        assistant_msg = result.scalar_one()
        assert assistant_msg.sources is not None
        sources = json.loads(assistant_msg.sources)
        assert note_id in sources
