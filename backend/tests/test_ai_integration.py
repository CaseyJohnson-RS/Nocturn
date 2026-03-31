"""Integration tests for the AI assistant module.

Tests cover: session CRUD, send message (Planner tool-loop with mock),
proposal lifecycle (apply/dismiss), bulk confirm/dismiss, cancel,
concurrency guard, and error handling.
"""

import json
import uuid
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.redis import redis_client
from app.config import settings
from app.modules.ai.models import ChatMessage, ChatSession
from app.modules.ai.service import _token_budget
from app.modules.ai.tools import make_proposal, make_pending_confirmation
from app.modules.auth.models import User


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

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


def _parse_sse(text: str) -> list[tuple[str | None, dict]]:
    """Parse SSE text into a list of (event_name, data_dict) tuples."""
    events = []
    current_event = None
    for line in text.strip().splitlines():
        line = line.strip()
        if not line:
            current_event = None
            continue
        if line.startswith("event: "):
            current_event = line.removeprefix("event: ").strip()
        elif line.startswith("data: "):
            payload = json.loads(line.removeprefix("data: "))
            events.append((current_event, payload))
            current_event = None
    return events


# Mock that simulates a simple text-only response (no tool calls)
def _mock_stream(*args, **kwargs):
    accumulator = kwargs.get("accumulator")

    async def _gen():
        for text in ["Hello", " from", " AI"]:
            if accumulator:
                accumulator.feed_delta({"content": text})
            yield text
        if accumulator:
            accumulator.finalize()
    return _gen()


# ---------------------------------------------------------------------------
# Token budget
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_token_budget_uses_configured_model_window(monkeypatch):
    monkeypatch.setattr(settings, "routerai_llm_context_window", 4096)
    assert await _token_budget() == 4096 - settings.system_prompt_tokens - settings.safety_margin_tokens


# ---------------------------------------------------------------------------
# Sessions
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Send message — Planner text-only (no tool calls)
# ---------------------------------------------------------------------------

class TestSendMessage:
    @patch("app.modules.ai.service.chat_completion_stream", side_effect=_mock_stream)
    async def test_send_message_streams_response(
        self, mock_chat, client: AsyncClient, db: AsyncSession,
    ):
        token = await register_and_login(client, db)
        session = await create_session(client, token)

        resp = await client.post(
            f"/api/ai/sessions/{session['id']}/messages",
            json={"message": "Hello AI"},
            headers=auth(token),
        )
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/event-stream")

        events = _parse_sse(resp.text)
        text_deltas = [(e, d) for e, d in events if e == "ai:text_delta"]
        done_events = [(e, d) for e, d in events if e == "ai:done"]

        assert len(text_deltas) >= 1
        assert len(done_events) == 1
        assert "message" in done_events[0][1]
        assert done_events[0][1]["message"]["role"] == "assistant"

    @patch("app.modules.ai.service.chat_completion_stream", side_effect=_mock_stream)
    async def test_send_message_saves_messages(
        self, mock_chat, client: AsyncClient, db: AsyncSession,
    ):
        token = await register_and_login(client, db)
        session = await create_session(client, token)

        await client.post(
            f"/api/ai/sessions/{session['id']}/messages",
            json={"message": "Hello AI"},
            headers=auth(token),
        )

        result = await db.execute(
            select(ChatMessage)
            .where(ChatMessage.session_id == session["id"])
            .order_by(ChatMessage.created_at)
        )
        messages = result.scalars().all()
        assert len(messages) == 2
        assert messages[0].role == "user"
        assert messages[0].content == "Hello AI"
        assert messages[1].role == "assistant"
        assert "Hello from AI" in messages[1].content

    @patch("app.modules.ai.service.chat_completion_stream", side_effect=_mock_stream)
    async def test_send_message_auto_titles_session(
        self, mock_chat, client: AsyncClient, db: AsyncSession,
    ):
        token = await register_and_login(client, db)
        session = await create_session(client, token)

        await client.post(
            f"/api/ai/sessions/{session['id']}/messages",
            json={"message": "How do I learn Python?"},
            headers=auth(token),
        )

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
    async def test_send_message_with_attached_notes(
        self, mock_chat, client: AsyncClient, db: AsyncSession,
    ):
        token = await register_and_login(client, db)

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

        result = await db.execute(
            select(ChatMessage)
            .where(ChatMessage.session_id == session["id"])
            .order_by(ChatMessage.created_at)
        )
        messages = result.scalars().all()
        assert messages[0].role == "user"
        assert messages[0].attached_note_ids == [uuid.UUID(note_id)]

    @patch("app.modules.ai.service.chat_completion_stream", side_effect=_mock_stream)
    async def test_send_message_handles_llm_failure(
        self, mock_chat, client: AsyncClient, db: AsyncSession,
    ):
        async def _broken_stream(*args, **kwargs):
            if False:
                yield ""
            raise RuntimeError("LLM error")

        mock_chat.side_effect = _broken_stream

        token = await register_and_login(client, db)
        session = await create_session(client, token)

        resp = await client.post(
            f"/api/ai/sessions/{session['id']}/messages",
            json={"message": "Hello AI"},
            headers=auth(token),
        )

        assert resp.status_code == 200
        events = _parse_sse(resp.text)
        error_events = [(e, d) for e, d in events if e == "ai:error"]
        assert len(error_events) >= 1

        # User message saved, no assistant message
        result = await db.execute(
            select(ChatMessage).where(ChatMessage.session_id == session["id"])
        )
        messages = result.scalars().all()
        assert len(messages) == 1
        assert messages[0].role == "user"

    @patch("app.modules.ai.service.chat_completion_stream", side_effect=_mock_stream)
    async def test_concurrency_guard_blocks_parallel(
        self, mock_chat, client: AsyncClient, db: AsyncSession,
    ):
        """Second send_message should get 409 while first is generating."""
        token = await register_and_login(client, db)
        session = await create_session(client, token)

        # Simulate a generating flag already set
        key = f"generating:{session['id']}"
        await redis_client.set(key, "1", ex=60)

        resp = await client.post(
            f"/api/ai/sessions/{session['id']}/messages",
            json={"message": "Another message"},
            headers=auth(token),
        )
        assert resp.status_code == 409

        # Clean up
        await redis_client.delete(key)


# ---------------------------------------------------------------------------
# Proposal lifecycle (apply / dismiss)
# ---------------------------------------------------------------------------

class TestProposalLifecycle:
    """Test PATCH /actions/{action_id} for applying/dismissing proposals."""

    async def _setup_message_with_proposal(
        self, client: AsyncClient, db: AsyncSession,
    ) -> tuple[str, dict, str]:
        """Create a session and directly insert an assistant message with a proposal.
        Returns (token, session_dict, proposal_id).
        """
        token = await register_and_login(client, db)
        session = await create_session(client, token)
        sid = session["id"]

        proposal = make_proposal("edit_note", str(uuid.uuid4()), {
            "title": "New Title",
            "content": "New content",
        })

        # Insert assistant message with the proposal
        msg = ChatMessage(
            session_id=uuid.UUID(sid),
            role="assistant",
            content="I suggest editing your note.",
            actions=[proposal],
            token_estimate=10,
        )
        db.add(msg)
        await db.commit()

        return token, session, proposal["id"], str(msg.id)

    async def test_apply_proposal(self, client: AsyncClient, db: AsyncSession):
        token, session, proposal_id, msg_id = await self._setup_message_with_proposal(client, db)
        sid = session["id"]

        resp = await client.patch(
            f"/api/ai/sessions/{sid}/messages/{msg_id}/actions/{proposal_id}",
            json={"status": "applied"},
            headers=auth(token),
        )
        assert resp.status_code == 200
        data = resp.json()

        # Proposal should be applied, data cleared, summary set
        applied = data["actions"][0]
        assert applied["status"] == "applied"
        assert applied["data"] is None
        assert applied["summary"] is not None

    async def test_dismiss_proposal(self, client: AsyncClient, db: AsyncSession):
        token, session, proposal_id, msg_id = await self._setup_message_with_proposal(client, db)
        sid = session["id"]

        resp = await client.patch(
            f"/api/ai/sessions/{sid}/messages/{msg_id}/actions/{proposal_id}",
            json={"status": "dismissed"},
            headers=auth(token),
        )
        assert resp.status_code == 200
        assert resp.json()["actions"][0]["status"] == "dismissed"

    async def test_double_apply_rejected(self, client: AsyncClient, db: AsyncSession):
        token, session, proposal_id, msg_id = await self._setup_message_with_proposal(client, db)
        sid = session["id"]

        # Apply once
        await client.patch(
            f"/api/ai/sessions/{sid}/messages/{msg_id}/actions/{proposal_id}",
            json={"status": "applied"},
            headers=auth(token),
        )

        # Try again — should get 409
        resp = await client.patch(
            f"/api/ai/sessions/{sid}/messages/{msg_id}/actions/{proposal_id}",
            json={"status": "applied"},
            headers=auth(token),
        )
        assert resp.status_code == 409

    async def test_invalid_action_status(self, client: AsyncClient, db: AsyncSession):
        token, session, proposal_id, msg_id = await self._setup_message_with_proposal(client, db)
        sid = session["id"]

        resp = await client.patch(
            f"/api/ai/sessions/{sid}/messages/{msg_id}/actions/{proposal_id}",
            json={"status": "invalid"},
            headers=auth(token),
        )
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Bulk confirm / dismiss
# ---------------------------------------------------------------------------

class TestBulkLifecycle:
    async def _setup_message_with_confirmation(
        self, client: AsyncClient, db: AsyncSession,
    ) -> tuple[str, dict, str]:
        token = await register_and_login(client, db)
        session = await create_session(client, token)
        sid = session["id"]

        note_id = str(uuid.uuid4())
        pc = make_pending_confirmation("add_tags", [note_id], {"tags": ["test"]})

        msg = ChatMessage(
            session_id=uuid.UUID(sid),
            role="assistant",
            content="I'll add tags to those notes.",
            actions=[pc],
            token_estimate=10,
        )
        db.add(msg)
        await db.commit()

        return token, session, pc["id"]

    async def test_dismiss_bulk(self, client: AsyncClient, db: AsyncSession):
        token, session, conf_id = await self._setup_message_with_confirmation(client, db)
        sid = session["id"]

        resp = await client.post(
            f"/api/ai/sessions/{sid}/dismiss/{conf_id}",
            headers=auth(token),
        )
        assert resp.status_code == 200
        data = resp.json()
        conf = [a for a in data["actions"] if a.get("type") == "pending_confirmation"][0]
        assert conf["status"] == "dismissed"
        assert conf["summary"] is not None

    async def test_dismiss_already_processed(self, client: AsyncClient, db: AsyncSession):
        token, session, conf_id = await self._setup_message_with_confirmation(client, db)
        sid = session["id"]

        await client.post(
            f"/api/ai/sessions/{sid}/dismiss/{conf_id}",
            headers=auth(token),
        )

        resp = await client.post(
            f"/api/ai/sessions/{sid}/dismiss/{conf_id}",
            headers=auth(token),
        )
        assert resp.status_code == 409


# ---------------------------------------------------------------------------
# Cancel
# ---------------------------------------------------------------------------

class TestCancel:
    async def test_cancel_no_active_operation(self, client: AsyncClient, db: AsyncSession):
        token = await register_and_login(client, db)
        session = await create_session(client, token)

        resp = await client.post(
            f"/api/ai/sessions/{session['id']}/cancel",
            headers=auth(token),
        )
        assert resp.status_code == 409

    async def test_cancel_active_operation(self, client: AsyncClient, db: AsyncSession):
        token = await register_and_login(client, db)
        session = await create_session(client, token)

        key = f"generating:{session['id']}"
        await redis_client.set(key, "1", ex=60)

        resp = await client.post(
            f"/api/ai/sessions/{session['id']}/cancel",
            headers=auth(token),
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "cancelled"

        # Key should be removed
        assert await redis_client.get(key) is None


# ---------------------------------------------------------------------------
# Tool executor unit tests
# ---------------------------------------------------------------------------

class TestToolExecutor:
    """Unit-level tests for ToolExecutor handlers."""

    async def test_search_notes_fulltext(self, client: AsyncClient, db: AsyncSession):
        token = await register_and_login(client, db)

        # Create a note
        await client.post("/api/notes", json={
            "title": "Cooking Tips",
            "content": "Always season your pasta water.",
        }, headers=auth(token))

        from app.modules.ai.tools import ToolExecutor
        from app.modules.auth.models import User as UserModel
        result = await db.execute(select(UserModel).where(UserModel.email == "ai@test.com"))
        user = result.scalar_one()

        actions: list[dict] = []
        executor = ToolExecutor(db, user.id, actions)
        result_str = await executor.execute(
            "search_notes",
            json.dumps({"query": "cooking", "search_mode": "fulltext", "limit": 5}),
        )
        data = json.loads(result_str)
        assert "notes" in data
        assert len(data["notes"]) >= 1
        assert data["notes"][0]["title"] == "Cooking Tips"

    async def test_get_note(self, client: AsyncClient, db: AsyncSession):
        token = await register_and_login(client, db)

        note_resp = await client.post("/api/notes", json={
            "title": "Get Me",
            "content": "Full content here.",
        }, headers=auth(token))
        note_id = note_resp.json()["id"]

        from app.modules.ai.tools import ToolExecutor
        from app.modules.auth.models import User as UserModel
        result = await db.execute(select(UserModel).where(UserModel.email == "ai@test.com"))
        user = result.scalar_one()

        actions: list[dict] = []
        executor = ToolExecutor(db, user.id, actions)
        result_str = await executor.execute("get_note", json.dumps({"note_id": note_id}))
        data = json.loads(result_str)
        assert data["title"] == "Get Me"
        assert data["content"] == "Full content here."

    async def test_propose_edit_note(self, client: AsyncClient, db: AsyncSession):
        token = await register_and_login(client, db)

        note_resp = await client.post("/api/notes", json={
            "title": "Edit Me",
            "content": "Original content.",
        }, headers=auth(token))
        note_id = note_resp.json()["id"]

        from app.modules.ai.tools import ToolExecutor
        from app.modules.auth.models import User as UserModel
        result = await db.execute(select(UserModel).where(UserModel.email == "ai@test.com"))
        user = result.scalar_one()

        actions: list[dict] = []
        executor = ToolExecutor(db, user.id, actions)
        result_str = await executor.execute(
            "propose_edit_note",
            json.dumps({"note_id": note_id, "title": "Edited Title"}),
        )
        data = json.loads(result_str)
        assert data["status"] == "registered"
        assert len(actions) == 1
        assert actions[0]["proposal_type"] == "edit_note"
        assert actions[0]["status"] == "pending"
        assert actions[0]["data"]["title"] == "Edited Title"

    async def test_propose_duplicate_rejected(self, client: AsyncClient, db: AsyncSession):
        token = await register_and_login(client, db)

        note_resp = await client.post("/api/notes", json={
            "title": "Dup Test",
            "content": "Content.",
        }, headers=auth(token))
        note_id = note_resp.json()["id"]

        from app.modules.ai.tools import ToolExecutor
        from app.modules.auth.models import User as UserModel
        result = await db.execute(select(UserModel).where(UserModel.email == "ai@test.com"))
        user = result.scalar_one()

        actions: list[dict] = []
        executor = ToolExecutor(db, user.id, actions)

        await executor.execute(
            "propose_edit_note",
            json.dumps({"note_id": note_id, "title": "First"}),
        )
        result_str = await executor.execute(
            "propose_edit_note",
            json.dumps({"note_id": note_id, "content": "Second"}),
        )
        data = json.loads(result_str)
        assert data["error"] == "duplicate_proposal"
        assert len(actions) == 1

    async def test_propose_create_note(self, client: AsyncClient, db: AsyncSession):
        token = await register_and_login(client, db)

        from app.modules.ai.tools import ToolExecutor
        from app.modules.auth.models import User as UserModel
        result = await db.execute(select(UserModel).where(UserModel.email == "ai@test.com"))
        user = result.scalar_one()

        actions: list[dict] = []
        executor = ToolExecutor(db, user.id, actions)
        result_str = await executor.execute(
            "propose_create_note",
            json.dumps({"title": "New Note", "content": "Content", "tags": ["tag1"]}),
        )
        data = json.loads(result_str)
        assert data["status"] == "registered"
        assert actions[0]["proposal_type"] == "create_note"
        assert actions[0]["data"]["tags"] == ["tag1"]


# ---------------------------------------------------------------------------
# Summary generation
# ---------------------------------------------------------------------------

class TestSummary:
    def test_build_summary_applied(self):
        from app.modules.ai.tools import _build_summary

        proposal = {
            "type": "proposal",
            "proposal_type": "edit_note",
            "data": {"title": "My Note"},
        }
        s = _build_summary(proposal, "applied")
        assert "My Note" in s
        assert "Edit" in s

    def test_build_summary_dismissed(self):
        from app.modules.ai.tools import _build_summary

        proposal = {
            "type": "proposal",
            "proposal_type": "delete_note",
            "data": {"note_title": "Old Note"},
        }
        s = _build_summary(proposal, "dismissed")
        assert "Dismissed" in s
        assert "Old Note" in s

    def test_build_summary_pending_confirmation(self):
        from app.modules.ai.tools import _build_summary

        pc = {
            "type": "pending_confirmation",
            "operation_type": "add_tags",
            "note_ids": ["a", "b", "c"],
        }
        s = _build_summary(pc, "dismissed")
        assert "3 notes" in s
        assert "dismissed" in s
