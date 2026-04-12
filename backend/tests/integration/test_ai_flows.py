"""Integration tests for AI assistant flows.


Tests cover: session CRUD, message sending with mocked LLM, proposal lifecycle,
bulk confirm/dismiss, cancel, streaming responses (SSE), and multi-user isolation.
"""

import json
import uuid
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.app.common.routerai import ChatCompletionAccumulator
from src.app.modules.auth.models import User

REGISTER = "/api/auth/register"
LOGIN = "/api/auth/login"
NOTES = "/api/notes"
SESSIONS = "/api/ai/sessions"

USER = {"email": "ai_user@example.com", "password": "Valid1pass", "nickname": "aiuser"}
USER2 = {"email": "ai_other@example.com", "password": "Valid1pass", "nickname": "aiother"}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _register_confirm_login(
    client: AsyncClient,
    db: AsyncSession,
    user_data: dict[str, str] = USER,
) -> str:
    with patch("src.app.modules.auth.service.send_confirmation_email", new_callable=AsyncMock):
        await client.post(REGISTER, json=user_data)

    result = await db.execute(select(User).where(User.email == user_data["email"]))
    user: User = result.scalar_one()
    user.is_email_confirmed = True
    await db.commit()

    resp = await client.post(
        LOGIN,
        json={"email": user_data["email"], "password": user_data["password"]},
    )
    return resp.json()["access_token"]


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _create_session(client: AsyncClient, token: str) -> dict[str, Any]:
    resp = await client.post(SESSIONS, json={}, headers=_auth(token))
    assert resp.status_code == 201
    return resp.json()


async def _create_note(
    client: AsyncClient,
    token: str,
    title: str = "Test Note",
    content: str = "Some content",
) -> dict[str, Any]:
    with patch("src.app.modules.rag.service.RAGRepository.enqueue", new_callable=AsyncMock):
        resp = await client.post(
            NOTES,
            json={"title": title, "content": content, "tag_ids": []},
            headers=_auth(token),
        )
    assert resp.status_code == 201
    return resp.json()


def _parse_sse(raw: str) -> list[dict[str, Any]]:
    """Parse an SSE text body into a list of {event, data} dicts."""
    events: list[dict[str, Any]] = []
    current_event = None
    for line in raw.split("\n"):
        if line.startswith("event: "):
            current_event = line.removeprefix("event: ").strip()
        elif line.startswith("data: "):
            payload = line.removeprefix("data: ").strip()
            events.append(
                {
                    "event": current_event,
                    "data": json.loads(payload),
                }
            )
            current_event = None
    return events


def _fake_llm_stream(
    content: str = "Ответ ассистента", tool_calls: list[dict[str, Any]] | None = None
):
    """Create a mock for chat_completion_stream that yields content tokens
    and optionally registers tool_calls on the accumulator."""

    async def _stream(
        messages: list[dict[str, Any]] | None,
        model: str | None = None,
        tools: list[dict[str, Any]] | None = None,
        accumulator: ChatCompletionAccumulator | None = None,
    ):
        for token in content.split():
            if accumulator:
                accumulator.feed_delta(SimpleNamespace(content=token + " ", tool_calls=None))
            yield token + " "
        if tool_calls and accumulator:
            for idx, tc in enumerate(tool_calls):
                accumulator.feed_delta(
                    SimpleNamespace(
                        content=None,
                        tool_calls=[
                            SimpleNamespace(
                                index=idx,
                                id=tc.get("id", f"call_{idx}"),
                                function=SimpleNamespace(
                                    name=tc["name"],
                                    arguments=json.dumps(tc.get("arguments", {})),
                                ),
                            )
                        ],
                    )
                )

    return _stream


async def _send_message_sse(
    client: AsyncClient,
    token: str,
    session_id: str,
    content: str = "Привет",
    attached_note_ids: list[str] | None = None,
) -> list[dict[str, Any]]:
    """Send a message via POST and parse the SSE response."""
    body: dict[str, Any] = {"content": content}
    if attached_note_ids:
        body["attached_note_ids"] = attached_note_ids

    resp = await client.post(
        f"{SESSIONS}/{session_id}/messages",
        json=body,
        headers=_auth(token),
    )
    assert resp.status_code == 200
    return _parse_sse(resp.text)


# ---------------------------------------------------------------------------
# Session CRUD
# ---------------------------------------------------------------------------


class TestSessionCRUD:
    @pytest.mark.anyio()
    async def test_create_session(self, client: AsyncClient, db: AsyncSession) -> None:
        token = await _register_confirm_login(client, db)

        session = await _create_session(client, token)

        assert "id" in session
        assert session["title"] is None
        assert session["last_message_at"] is None

    @pytest.mark.anyio()
    async def test_list_sessions(self, client: AsyncClient, db: AsyncSession) -> None:
        token = await _register_confirm_login(client, db)

        await _create_session(client, token)
        await _create_session(client, token)

        resp = await client.get(SESSIONS, headers=_auth(token))

        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2
        assert len(data["items"]) == 2

    @pytest.mark.anyio()
    async def test_list_sessions_pagination(
        self,
        client: AsyncClient,
        db: AsyncSession,
    ) -> None:
        token = await _register_confirm_login(client, db)

        for _ in range(5):
            await _create_session(client, token)

        resp = await client.get(
            SESSIONS,
            params={"limit": 2, "offset": 1},
            headers=_auth(token),
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 5
        assert len(data["items"]) == 2

    @pytest.mark.anyio()
    async def test_delete_session(self, client: AsyncClient, db: AsyncSession) -> None:
        token = await _register_confirm_login(client, db)
        session = await _create_session(client, token)

        resp = await client.delete(
            f"{SESSIONS}/{session['id']}",
            headers=_auth(token),
        )

        assert resp.status_code == 204

        resp = await client.get(SESSIONS, headers=_auth(token))
        assert resp.json()["total"] == 0

    @pytest.mark.anyio()
    async def test_delete_nonexistent_session(
        self,
        client: AsyncClient,
        db: AsyncSession,
    ) -> None:
        token = await _register_confirm_login(client, db)

        resp = await client.delete(
            f"{SESSIONS}/{uuid.uuid4()}",
            headers=_auth(token),
        )

        assert resp.status_code == 404

    @pytest.mark.anyio()
    async def test_update_session_title(
        self,
        client: AsyncClient,
        db: AsyncSession,
    ) -> None:
        token = await _register_confirm_login(client, db)
        session = await _create_session(client, token)

        resp = await client.put(
            f"{SESSIONS}/{session['id']}",
            json={"title": "My Chat"},
            headers=_auth(token),
        )

        assert resp.status_code == 200
        assert resp.json()["title"] == "My Chat"


# ---------------------------------------------------------------------------
# Send message & LLM interaction
# ---------------------------------------------------------------------------


class TestSendMessage:
    @pytest.mark.anyio()
    async def test_send_message_and_receive_sse(
        self,
        client: AsyncClient,
        db: AsyncSession,
    ) -> None:
        """Full flow: send a message, mock LLM returns text, get SSE events."""
        token = await _register_confirm_login(client, db)
        session = await _create_session(client, token)

        with patch(
            "src.app.modules.ai.service.chat_completion_stream",
            side_effect=_fake_llm_stream("Привет! Как дела?"),
        ):
            events = await _send_message_sse(client, token, session["id"])

        event_types = [e["event"] for e in events]
        assert "ai:text_delta" in event_types
        assert event_types[-1] == "ai:done"

    @pytest.mark.anyio()
    async def test_messages_persisted(
        self,
        client: AsyncClient,
        db: AsyncSession,
    ) -> None:
        token = await _register_confirm_login(client, db)
        session = await _create_session(client, token)

        with patch(
            "src.app.modules.ai.service.chat_completion_stream",
            side_effect=_fake_llm_stream("Ответ"),
        ):
            await _send_message_sse(client, token, session["id"], content="Привет")

        resp = await client.get(
            f"{SESSIONS}/{session['id']}/messages",
            headers=_auth(token),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2  # user + assistant
        assert data["items"][0]["role"] == "user"
        assert data["items"][0]["content"] == "Привет"
        assert data["items"][1]["role"] == "assistant"

    @pytest.mark.anyio()
    async def test_auto_title_from_first_message(
        self,
        client: AsyncClient,
        db: AsyncSession,
    ) -> None:
        token = await _register_confirm_login(client, db)
        session = await _create_session(client, token)

        with patch(
            "src.app.modules.ai.service.chat_completion_stream",
            side_effect=_fake_llm_stream("OK"),
        ):
            await _send_message_sse(
                client,
                token,
                session["id"],
                content="Помоги с заметками",
            )

        resp = await client.get(SESSIONS, headers=_auth(token))
        updated = resp.json()["items"][0]
        assert updated["title"] == "Помоги с заметками"
        assert updated["last_message_at"] is not None

    @pytest.mark.anyio()
    async def test_send_to_nonexistent_session(
        self,
        client: AsyncClient,
        db: AsyncSession,
    ) -> None:
        token = await _register_confirm_login(client, db)

        resp = await client.post(
            f"{SESSIONS}/{uuid.uuid4()}/messages",
            json={"content": "Hello"},
            headers=_auth(token),
        )

        assert resp.status_code == 404

    @pytest.mark.anyio()
    async def test_send_with_attached_notes(
        self,
        client: AsyncClient,
        db: AsyncSession,
    ) -> None:
        token = await _register_confirm_login(client, db)
        session = await _create_session(client, token)
        note = await _create_note(client, token, title="Моя заметка")

        with patch(
            "src.app.modules.ai.service.chat_completion_stream",
            side_effect=_fake_llm_stream("Вот ваша заметка"),
        ):
            events = await _send_message_sse(
                client,
                token,
                session["id"],
                content="Что в заметке?",
                attached_note_ids=[note["id"]],
            )

        assert any(e["event"] == "ai:done" for e in events)

        # Check user message has attached_note_ids
        resp = await client.get(
            f"{SESSIONS}/{session['id']}/messages",
            headers=_auth(token),
        )
        user_msg = resp.json()["items"][0]
        assert user_msg["attached_note_ids"] == [note["id"]]


# ---------------------------------------------------------------------------
# Messages pagination
# ---------------------------------------------------------------------------


class TestMessagesPagination:
    @pytest.mark.anyio()
    async def test_paginated_messages(
        self,
        client: AsyncClient,
        db: AsyncSession,
    ) -> None:
        token = await _register_confirm_login(client, db)
        session = await _create_session(client, token)

        # Send 3 messages
        for i in range(3):
            with patch(
                "src.app.modules.ai.service.chat_completion_stream",
                side_effect=_fake_llm_stream(f"Ответ {i}"),
            ):
                await _send_message_sse(
                    client,
                    token,
                    session["id"],
                    content=f"Вопрос {i}",
                )

        # 6 messages total (3 user + 3 assistant)
        resp = await client.get(
            f"{SESSIONS}/{session['id']}/messages",
            params={"limit": 2, "offset": 0},
            headers=_auth(token),
        )

        data = resp.json()
        assert data["total"] == 6
        assert len(data["items"]) == 2


# ---------------------------------------------------------------------------
# Proposal lifecycle
# ---------------------------------------------------------------------------


class TestProposalLifecycle:
    @pytest.mark.anyio()
    async def test_propose_and_apply(
        self,
        client: AsyncClient,
        db: AsyncSession,
    ) -> None:
        """LLM calls propose_edit_note → proposal emitted via SSE → user applies."""
        token = await _register_confirm_login(client, db)
        session = await _create_session(client, token)
        note = await _create_note(client, token, title="Old Title")

        tool_calls: list[dict[str, Any]] = [
            {
                "name": "propose_edit_note",
                "arguments": {"note_id": note["id"], "title": "New Title"},
            }
        ]

        with patch(
            "src.app.modules.ai.service.chat_completion_stream",
            side_effect=_fake_llm_stream("Предлагаю изменить заголовок", tool_calls),
        ):
            events = await _send_message_sse(
                client,
                token,
                session["id"],
                content="Переименуй заметку",
            )

        proposals = [e for e in events if e["event"] == "ai:proposal"]
        assert len(proposals) == 1
        proposal = proposals[0]["data"]
        assert proposal["proposal_type"] == "edit_note"
        assert proposal["status"] == "pending"

        # Get the assistant message
        resp = await client.get(
            f"{SESSIONS}/{session['id']}/messages",
            headers=_auth(token),
        )
        assistant_msg = [m for m in resp.json()["items"] if m["role"] == "assistant"][0]

        # Apply the proposal
        resp = await client.patch(
            f"{SESSIONS}/{session['id']}/messages/{assistant_msg['id']}/actions/{proposal['id']}",
            json={"status": "applied"},
            headers=_auth(token),
        )

        assert resp.status_code == 200
        updated_action = next(a for a in resp.json()["actions"] if a["id"] == proposal["id"])
        assert updated_action["status"] == "applied"
        assert updated_action["data"] is None  # cleared after apply
        assert updated_action["summary"] is not None

    @pytest.mark.anyio()
    async def test_dismiss_proposal(
        self,
        client: AsyncClient,
        db: AsyncSession,
    ) -> None:
        token = await _register_confirm_login(client, db)
        session = await _create_session(client, token)
        note = await _create_note(client, token)

        tool_calls: list[dict[str, Any]] = [
            {
                "name": "propose_delete_note",
                "arguments": {"note_id": note["id"]},
            }
        ]

        with patch(
            "src.app.modules.ai.service.chat_completion_stream",
            side_effect=_fake_llm_stream("Удалить?", tool_calls),
        ):
            events = await _send_message_sse(
                client,
                token,
                session["id"],
                content="Удали заметку",
            )

        proposal = [e for e in events if e["event"] == "ai:proposal"][0]["data"]

        resp = await client.get(
            f"{SESSIONS}/{session['id']}/messages",
            headers=_auth(token),
        )
        msg = [m for m in resp.json()["items"] if m["role"] == "assistant"][0]

        resp = await client.patch(
            f"{SESSIONS}/{session['id']}/messages/{msg['id']}/actions/{proposal['id']}",
            json={"status": "dismissed"},
            headers=_auth(token),
        )

        assert resp.status_code == 200
        action = next(a for a in resp.json()["actions"] if a["id"] == proposal["id"])
        assert action["status"] == "dismissed"

    @pytest.mark.anyio()
    async def test_cannot_apply_twice(
        self,
        client: AsyncClient,
        db: AsyncSession,
    ) -> None:
        token = await _register_confirm_login(client, db)
        session = await _create_session(client, token)
        note = await _create_note(client, token)

        tool_calls: list[dict[str, Any]] = [
            {
                "name": "propose_edit_note",
                "arguments": {"note_id": note["id"], "title": "X"},
            }
        ]

        with patch(
            "src.app.modules.ai.service.chat_completion_stream",
            side_effect=_fake_llm_stream("OK", tool_calls),
        ):
            events = await _send_message_sse(
                client,
                token,
                session["id"],
                content="Edit",
            )

        proposal = [e for e in events if e["event"] == "ai:proposal"][0]["data"]

        resp = await client.get(
            f"{SESSIONS}/{session['id']}/messages",
            headers=_auth(token),
        )
        msg = [m for m in resp.json()["items"] if m["role"] == "assistant"][0]

        url = f"{SESSIONS}/{session['id']}/messages/{msg['id']}/actions/{proposal['id']}"

        # First apply succeeds
        resp = await client.patch(url, json={"status": "applied"}, headers=_auth(token))
        assert resp.status_code == 200

        # Second apply fails
        resp = await client.patch(url, json={"status": "applied"}, headers=_auth(token))
        assert resp.status_code == 409


# ---------------------------------------------------------------------------
# Pending actions block new messages (409)
# ---------------------------------------------------------------------------


class TestPendingActionsBlock:
    @pytest.mark.anyio()
    async def test_pending_proposals_block_send(
        self,
        client: AsyncClient,
        db: AsyncSession,
    ) -> None:
        """AIS 9.2: cannot send a new message while proposals are pending."""
        token = await _register_confirm_login(client, db)
        session = await _create_session(client, token)
        note = await _create_note(client, token)

        tool_calls: list[dict[str, Any]] = [
            {
                "name": "propose_edit_note",
                "arguments": {"note_id": note["id"], "content": "changed"},
            }
        ]

        with patch(
            "src.app.modules.ai.service.chat_completion_stream",
            side_effect=_fake_llm_stream("Proposal", tool_calls),
        ):
            await _send_message_sse(client, token, session["id"])

        # Try to send another message — should be blocked
        resp = await client.post(
            f"{SESSIONS}/{session['id']}/messages",
            json={"content": "New question"},
            headers=_auth(token),
        )

        assert resp.status_code == 409


# ---------------------------------------------------------------------------
# Bulk operations (confirm / dismiss)
# ---------------------------------------------------------------------------


class TestBulkOperations:
    @pytest.mark.anyio()
    async def test_batch_add_tags_confirm_and_dismiss(
        self,
        client: AsyncClient,
        db: AsyncSession,
    ) -> None:
        token = await _register_confirm_login(client, db)
        session = await _create_session(client, token)
        note = await _create_note(client, token)

        tool_calls: list[dict[str, Any]] = [
            {
                "name": "batch_add_tags",
                "arguments": {"note_ids": [note["id"]], "tags": ["work"]},
            }
        ]

        with patch(
            "src.app.modules.ai.service.chat_completion_stream",
            side_effect=_fake_llm_stream("Добавляю теги", tool_calls),
        ):
            events = await _send_message_sse(
                client,
                token,
                session["id"],
                content="Добавь тег work",
            )

        confirmations = [e for e in events if e["event"] == "ai:pending_confirmation"]
        assert len(confirmations) == 1
        cid = confirmations[0]["data"]["id"]

        # Dismiss it
        resp = await client.post(
            f"{SESSIONS}/{session['id']}/dismiss/{cid}",
            headers=_auth(token),
        )
        assert resp.status_code == 200

        dismissed = next(a for a in resp.json()["actions"] if a["id"] == cid)
        assert dismissed["status"] == "dismissed"

    @pytest.mark.anyio()
    async def test_confirm_nonexistent(
        self,
        client: AsyncClient,
        db: AsyncSession,
    ) -> None:
        token = await _register_confirm_login(client, db)
        session = await _create_session(client, token)

        resp = await client.post(
            f"{SESSIONS}/{session['id']}/confirm/{uuid.uuid4()}",
            headers=_auth(token),
        )

        # Bug 1 fix: error returned as JSON, not broken SSE
        assert resp.status_code == 404
        assert "detail" in resp.json()

    @pytest.mark.anyio()
    async def test_dismiss_nonexistent(
        self,
        client: AsyncClient,
        db: AsyncSession,
    ) -> None:
        token = await _register_confirm_login(client, db)
        session = await _create_session(client, token)

        resp = await client.post(
            f"{SESSIONS}/{session['id']}/dismiss/{uuid.uuid4()}",
            headers=_auth(token),
        )

        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Cancel generation
# ---------------------------------------------------------------------------


class TestCancelGeneration:
    @pytest.mark.anyio()
    async def test_cancel_no_active_operation(
        self,
        client: AsyncClient,
        db: AsyncSession,
    ) -> None:
        """No generating key in Redis → 409."""
        token = await _register_confirm_login(client, db)
        session = await _create_session(client, token)

        resp = await client.post(
            f"{SESSIONS}/{session['id']}/cancel",
            headers=_auth(token),
        )

        assert resp.status_code == 409


# ---------------------------------------------------------------------------
# Create session with dismiss
# ---------------------------------------------------------------------------


class TestCreateWithDismiss:
    @pytest.mark.anyio()
    async def test_dismiss_pending_on_new_session(
        self,
        client: AsyncClient,
        db: AsyncSession,
    ) -> None:
        """AIS 10.2: creating a new session dismisses pending actions in old one."""
        token = await _register_confirm_login(client, db)
        old_session = await _create_session(client, token)
        note = await _create_note(client, token)

        tool_calls: list[dict[str, Any]] = [
            {
                "name": "propose_edit_note",
                "arguments": {"note_id": note["id"], "title": "X"},
            }
        ]

        with patch(
            "src.app.modules.ai.service.chat_completion_stream",
            side_effect=_fake_llm_stream("Edit", tool_calls),
        ):
            await _send_message_sse(client, token, old_session["id"])

        # Create new session with dismiss
        resp = await client.post(
            SESSIONS,
            json={"dismiss_session_id": old_session["id"]},
            headers=_auth(token),
        )
        assert resp.status_code == 201

        # Check old session proposals are dismissed
        resp = await client.get(
            f"{SESSIONS}/{old_session['id']}/messages",
            headers=_auth(token),
        )
        assistant_msgs = [m for m in resp.json()["items"] if m["role"] == "assistant"]
        for msg in assistant_msgs:
            if msg["actions"]:
                for action in msg["actions"]:
                    assert action["status"] == "dismissed"


# ---------------------------------------------------------------------------
# Multi-user isolation
# ---------------------------------------------------------------------------


class TestIsolation:
    @pytest.mark.anyio()
    async def test_cannot_access_other_users_session(
        self,
        client: AsyncClient,
        db: AsyncSession,
    ) -> None:
        token1 = await _register_confirm_login(client, db, USER)
        token2 = await _register_confirm_login(client, db, USER2)

        session = await _create_session(client, token1)

        # User 2 cannot see user 1's sessions
        resp = await client.get(SESSIONS, headers=_auth(token2))
        assert resp.json()["total"] == 0

        # User 2 cannot delete user 1's session
        resp = await client.delete(
            f"{SESSIONS}/{session['id']}",
            headers=_auth(token2),
        )
        assert resp.status_code == 404

        # User 2 cannot send messages to user 1's session
        resp = await client.post(
            f"{SESSIONS}/{session['id']}/messages",
            json={"content": "Hack"},
            headers=_auth(token2),
        )
        assert resp.status_code == 404

    @pytest.mark.anyio()
    async def test_cannot_read_other_users_messages(
        self,
        client: AsyncClient,
        db: AsyncSession,
    ) -> None:
        token1 = await _register_confirm_login(client, db, USER)
        token2 = await _register_confirm_login(client, db, USER2)

        session = await _create_session(client, token1)

        with patch(
            "src.app.modules.ai.service.chat_completion_stream",
            side_effect=_fake_llm_stream("Secret"),
        ):
            await _send_message_sse(client, token1, session["id"])

        resp = await client.get(
            f"{SESSIONS}/{session['id']}/messages",
            headers=_auth(token2),
        )
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Auth required
# ---------------------------------------------------------------------------


class TestAuthRequired:
    @pytest.mark.anyio()
    async def test_all_endpoints_require_auth(
        self,
        client: AsyncClient,
        db: AsyncSession,
    ) -> None:
        token = await _register_confirm_login(client, db)
        session = await _create_session(client, token)
        sid = session["id"]

        for method, url in [
            ("POST", SESSIONS),
            ("GET", SESSIONS),
            ("DELETE", f"{SESSIONS}/{sid}"),
            ("PUT", f"{SESSIONS}/{sid}"),
            ("GET", f"{SESSIONS}/{sid}/messages"),
            ("POST", f"{SESSIONS}/{sid}/messages"),
            ("POST", f"{SESSIONS}/{sid}/cancel"),
            ("PATCH", f"{SESSIONS}/{sid}/messages/{uuid.uuid4()}/actions/x"),
            ("POST", f"{SESSIONS}/{sid}/confirm/x"),
            ("POST", f"{SESSIONS}/{sid}/dismiss/x"),
        ]:
            resp = await client.request(method, url)
            assert resp.status_code == 401, f"{method} {url} should be 401"
