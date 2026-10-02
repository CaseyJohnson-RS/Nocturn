"""Unit tests for AIService."""


import asyncio
import json
import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.app.common.exceptions import ConflictError, NotFoundError, ValidationError
from src.app.modules.ai.schemas import MessageResponse, SessionResponse
from src.app.modules.ai.service import (
    AIService,
    _actions_summary_for_context,
    _clear_cancel,
    _clear_generating,
    _estimate_tokens,
    _format_sse_event,
    _is_cancelled,
    _set_cancel,
    _set_generating,
    _stream_with_first_token_timeout,
)

# --- Helpers ---


def _mock_session(
    session_id: uuid.UUID | None = None,
    user_id: uuid.UUID | None = None,
    title: str | None = None,
) -> MagicMock:
    s = MagicMock()
    s.id = session_id or uuid.uuid4()
    s.user_id = user_id or uuid.uuid4()
    s.title = title
    s.created_at = datetime.now(UTC)
    s.last_message_at = None
    return s


def _mock_message(
    message_id: uuid.UUID | None = None,
    session_id: uuid.UUID | None = None,
    role: str = "assistant",
    content: str = "Hello",
    actions: list | None = None,
    attached_note_ids: list | None = None,
    token_estimate: int = 10,
) -> MagicMock:
    m = MagicMock()
    m.id = message_id or uuid.uuid4()
    m.session_id = session_id or uuid.uuid4()
    m.role = role
    m.content = content
    m.actions = actions
    m.attached_note_ids = attached_note_ids
    m.token_estimate = token_estimate
    m.created_at = datetime.now(UTC)
    return m


# --- Fixtures ---


@pytest.fixture()
def repo() -> AsyncMock:
    return AsyncMock()


@pytest.fixture()
def notes_repo() -> AsyncMock:
    return AsyncMock()


@pytest.fixture()
def rag() -> AsyncMock:
    return AsyncMock()


@pytest.fixture()
def service(repo: AsyncMock, notes_repo: AsyncMock, rag: AsyncMock) -> AIService:
    svc = AIService.__new__(AIService)
    svc.repo = repo
    svc.notes_repo = notes_repo
    svc.rag = rag
    svc.db = MagicMock()
    return svc


@pytest.fixture()
def user_id() -> uuid.UUID:
    return uuid.uuid4()


@pytest.fixture()
def session_id() -> uuid.UUID:
    return uuid.uuid4()


# =====================================================================
# Pure helpers
# =====================================================================


class TestEstimateTokens:
    def test_basic(self) -> None:
        with patch("src.app.modules.ai.service.settings") as mock_settings:
            mock_settings.planner_chars_per_token = 1.3
            result = _estimate_tokens("Hello world")
            assert result == int(len("Hello world") / 1.3)

    def test_empty(self) -> None:
        with patch("src.app.modules.ai.service.settings") as mock_settings:
            mock_settings.planner_chars_per_token = 1.3
            assert _estimate_tokens("") == 0


class TestFormatSSEEvent:
    def test_with_event(self) -> None:
        result = _format_sse_event({"delta": "hi"}, event="ai:text_delta")
        assert result == 'event: ai:text_delta\ndata: {"delta": "hi"}\n\n'

    def test_without_event(self) -> None:
        result = _format_sse_event({"key": "val"})
        assert result == 'data: {"key": "val"}\n\n'

    def test_serializes_uuid(self) -> None:
        uid = uuid.uuid4()
        result = _format_sse_event({"id": uid})
        assert str(uid) in result


class TestActionsSummaryForContext:
    def test_proposal_with_summary(self) -> None:
        actions = [
            {
                "type": "proposal",
                "proposal_type": "edit_note",
                "status": "pending",
                "summary": "Edit title",
            },
        ]
        result = _actions_summary_for_context(actions)
        assert "edit_note" in result
        assert "pending" in result
        assert "Edit title" in result

    def test_pending_confirmation(self) -> None:
        actions = [
            {
                "type": "pending_confirmation",
                "operation_type": "add_tags",
                "status": "pending",
                "note_ids": ["a", "b", "c"],
            },
        ]
        result = _actions_summary_for_context(actions)
        assert "add_tags" in result
        assert "3" in result

    def test_none_actions(self) -> None:
        assert _actions_summary_for_context(None) == ""

    def test_empty_list(self) -> None:
        assert _actions_summary_for_context([]) == ""

    def test_non_dict_entries_skipped(self) -> None:
        assert _actions_summary_for_context(["not a dict"]) == ""


# =====================================================================
# Redis generating flag
# =====================================================================


class TestGeneratingFlag:
    @pytest.mark.anyio()
    async def test_set_and_clear(self, session_id: uuid.UUID) -> None:
        with patch("src.app.modules.ai.service.redis_client") as mock_redis:
            mock_redis.set = AsyncMock(return_value=True)
            mock_redis.delete = AsyncMock()

            assert await _set_generating(session_id) is True
            mock_redis.set.assert_called_once()

            await _clear_generating(session_id)
            mock_redis.delete.assert_called_once()

    @pytest.mark.anyio()
    async def test_set_returns_false_when_locked(self, session_id: uuid.UUID) -> None:
        with patch("src.app.modules.ai.service.redis_client") as mock_redis:
            mock_redis.set = AsyncMock(return_value=None)
            assert await _set_generating(session_id) is False


# =====================================================================
# Cancellation via Redis
# =====================================================================


class TestCancelRedis:
    @pytest.mark.anyio()
    async def test_set_and_check(self) -> None:
        sid = uuid.uuid4()
        with patch("src.app.modules.ai.service.redis_client") as mock_redis:
            mock_redis.set = AsyncMock()
            mock_redis.exists = AsyncMock(return_value=1)

            await _set_cancel(sid)
            mock_redis.set.assert_called_once()

            assert await _is_cancelled(sid) is True

    @pytest.mark.anyio()
    async def test_not_cancelled(self) -> None:
        sid = uuid.uuid4()
        with patch("src.app.modules.ai.service.redis_client") as mock_redis:
            mock_redis.exists = AsyncMock(return_value=0)
            assert await _is_cancelled(sid) is False

    @pytest.mark.anyio()
    async def test_clear_cancel(self) -> None:
        sid = uuid.uuid4()
        with patch("src.app.modules.ai.service.redis_client") as mock_redis:
            mock_redis.delete = AsyncMock()
            await _clear_cancel(sid)
            mock_redis.delete.assert_called_once()


# =====================================================================
# First-token timeout wrapper
# =====================================================================


class TestStreamWithFirstTokenTimeout:
    @pytest.mark.anyio()
    async def test_normal_stream(self) -> None:
        async def gen():
            yield "a"
            yield "b"

        chunks = []
        async for c in _stream_with_first_token_timeout(gen(), 5.0):
            chunks.append(c)
        assert chunks == ["a", "b"]

    @pytest.mark.anyio()
    async def test_empty_stream(self) -> None:
        async def gen():
            return
            yield  # noqa: unreachable

        chunks = []
        async for c in _stream_with_first_token_timeout(gen(), 5.0):
            chunks.append(c)
        assert chunks == []

    @pytest.mark.anyio()
    async def test_timeout_on_first_token(self) -> None:
        from src.app.modules.ai.service import _LLMTimeoutError

        async def gen():
            await asyncio.sleep(100)
            yield "never"

        with pytest.raises(_LLMTimeoutError):
            async for _ in _stream_with_first_token_timeout(gen(), 0.01):
                pass


# =====================================================================
# Session management
# =====================================================================


class TestCreateSession:
    @pytest.mark.anyio()
    async def test_success(
        self, service: AIService, repo: AsyncMock, user_id: uuid.UUID,
    ) -> None:
        repo.count_user_sessions.return_value = 0
        session = _mock_session(user_id=user_id)
        repo.create_session.return_value = session

        result = await service.create_session(user_id)

        repo.create_session.assert_called_once_with(user_id)
        assert isinstance(result, SessionResponse)

    @pytest.mark.anyio()
    async def test_limit_reached(
        self, service: AIService, repo: AsyncMock, user_id: uuid.UUID,
    ) -> None:
        repo.count_user_sessions.return_value = 9999

        with pytest.raises(ConflictError, match="limit"):
            await service.create_session(user_id)

    @pytest.mark.anyio()
    async def test_dismiss_old_session(
        self, service: AIService, repo: AsyncMock, user_id: uuid.UUID,
    ) -> None:
        old_sid = uuid.uuid4()
        old_session = _mock_session(session_id=old_sid, user_id=user_id)
        repo.get_session.return_value = old_session
        repo.get_recent_messages.return_value = []
        repo.count_user_sessions.return_value = 0
        new_session = _mock_session(user_id=user_id)
        repo.create_session.return_value = new_session

        await service.create_session(user_id, dismiss_session_id=old_sid)

        repo.get_session.assert_called()
        repo.create_session.assert_called_once()


class TestListSessions:
    @pytest.mark.anyio()
    async def test_returns_list(
        self, service: AIService, repo: AsyncMock, user_id: uuid.UUID,
    ) -> None:
        sessions = [_mock_session(user_id=user_id), _mock_session(user_id=user_id)]
        repo.list_sessions.return_value = (sessions, 2)

        result = await service.list_sessions(user_id)

        assert result.total == 2
        assert len(result.items) == 2

    @pytest.mark.anyio()
    async def test_empty(
        self, service: AIService, repo: AsyncMock, user_id: uuid.UUID,
    ) -> None:
        repo.list_sessions.return_value = ([], 0)

        result = await service.list_sessions(user_id)

        assert result.items == []
        assert result.total == 0


class TestGetMessages:
    @pytest.mark.anyio()
    async def test_success(
        self,
        service: AIService,
        repo: AsyncMock,
        user_id: uuid.UUID,
        session_id: uuid.UUID,
    ) -> None:
        repo.get_session.return_value = _mock_session(session_id=session_id)
        msgs = [_mock_message(session_id=session_id)]
        repo.get_messages_paginated.return_value = (msgs, 1)

        result = await service.get_messages(user_id, session_id)

        assert result.total == 1

    @pytest.mark.anyio()
    async def test_session_not_found(
        self,
        service: AIService,
        repo: AsyncMock,
        user_id: uuid.UUID,
        session_id: uuid.UUID,
    ) -> None:
        repo.get_session.return_value = None

        with pytest.raises(NotFoundError):
            await service.get_messages(user_id, session_id)


class TestUpdateSession:
    @pytest.mark.anyio()
    async def test_success(
        self, service: AIService, repo: AsyncMock, user_id: uuid.UUID,
    ) -> None:
        session = _mock_session(user_id=user_id)
        repo.get_session.return_value = session
        updated = _mock_session(user_id=user_id)
        updated.title = "New title"
        repo.update_session_title.return_value = updated

        result = await service.update_session(user_id, session.id, "New title")

        assert result.title == "New title"

    @pytest.mark.anyio()
    async def test_not_found(
        self, service: AIService, repo: AsyncMock, user_id: uuid.UUID,
    ) -> None:
        repo.get_session.return_value = None

        with pytest.raises(NotFoundError):
            await service.update_session(user_id, uuid.uuid4(), "Title")


class TestDeleteSession:
    @pytest.mark.anyio()
    async def test_success(
        self, service: AIService, repo: AsyncMock, user_id: uuid.UUID,
    ) -> None:
        session = _mock_session(user_id=user_id)
        repo.get_session.return_value = session

        await service.delete_session(user_id, session.id)

        repo.delete_session.assert_called_once_with(session)

    @pytest.mark.anyio()
    async def test_not_found(
        self, service: AIService, repo: AsyncMock, user_id: uuid.UUID,
    ) -> None:
        repo.get_session.return_value = None

        with pytest.raises(NotFoundError):
            await service.delete_session(user_id, uuid.uuid4())


# =====================================================================
# pre_validate_send
# =====================================================================


class TestPreValidateSend:
    @pytest.mark.anyio()
    async def test_success(
        self, service: AIService, repo: AsyncMock, user_id: uuid.UUID,
        session_id: uuid.UUID,
    ) -> None:
        repo.get_session.return_value = _mock_session(session_id=session_id)
        repo.has_pending_actions.return_value = False

        result = await service.pre_validate_send(user_id, session_id, "Hi")

        assert result is None

    @pytest.mark.anyio()
    async def test_session_not_found(
        self, service: AIService, repo: AsyncMock, user_id: uuid.UUID,
        session_id: uuid.UUID,
    ) -> None:
        repo.get_session.return_value = None

        result = await service.pre_validate_send(user_id, session_id, "Hi")

        assert result is not None
        assert result[0] == 404

    @pytest.mark.anyio()
    async def test_message_too_long(
        self, service: AIService, repo: AsyncMock, user_id: uuid.UUID,
        session_id: uuid.UUID,
    ) -> None:
        repo.get_session.return_value = _mock_session(session_id=session_id)

        with patch("src.app.modules.ai.service.settings") as mock_s:
            mock_s.max_message_length = 10
            result = await service.pre_validate_send(
                user_id, session_id, "A" * 100,
            )

        assert result is not None
        assert result[0] == 400

    @pytest.mark.anyio()
    async def test_pending_actions_conflict(
        self, service: AIService, repo: AsyncMock, user_id: uuid.UUID,
        session_id: uuid.UUID,
    ) -> None:
        repo.get_session.return_value = _mock_session(session_id=session_id)
        repo.has_pending_actions.return_value = True

        result = await service.pre_validate_send(user_id, session_id, "Hi")

        assert result is not None
        assert result[0] == 409

    @pytest.mark.anyio()
    async def test_no_side_effects(
        self, service: AIService, repo: AsyncMock, user_id: uuid.UUID,
        session_id: uuid.UUID,
    ) -> None:
        """Bug 5 fix: pre_validate_send must not set the generating flag."""
        repo.get_session.return_value = _mock_session(session_id=session_id)
        repo.has_pending_actions.return_value = False

        with patch("src.app.modules.ai.service.redis_client") as mock_redis:
            await service.pre_validate_send(user_id, session_id, "Hi")
            mock_redis.set.assert_not_called()


# =====================================================================
# send_message (SSE generator)
# =====================================================================


class TestSendMessage:
    @pytest.mark.anyio()
    async def test_conflict_when_already_generating(
        self, service: AIService, user_id: uuid.UUID, session_id: uuid.UUID,
    ) -> None:
        """If Redis lock is taken, yield error + done."""
        with patch("src.app.modules.ai.service._set_generating", return_value=False):
            events = []
            async for chunk in service.send_message(
                user_id, session_id, "Hello",
            ):
                events.append(chunk)

        assert len(events) == 2
        assert "ai:error" in events[0]
        assert "conflict" in events[0]
        assert "ai:done" in events[1]

    @pytest.mark.anyio()
    async def test_session_not_found_inside_generator(
        self, service: AIService, repo: AsyncMock,
        user_id: uuid.UUID, session_id: uuid.UUID,
    ) -> None:
        repo.get_session.return_value = None

        with (
            patch("src.app.modules.ai.service._set_generating", return_value=True),
            patch("src.app.modules.ai.service._clear_generating", new_callable=AsyncMock),
            patch("src.app.modules.ai.service._clear_cancel", new_callable=AsyncMock),
        ):
            events = []
            async for chunk in service.send_message(
                user_id, session_id, "Hello",
            ):
                events.append(chunk)

        assert any("not_found" in e for e in events)
        assert any("ai:done" in e for e in events)

    @pytest.mark.anyio()
    async def test_generating_flag_always_cleared(
        self, service: AIService, repo: AsyncMock,
        user_id: uuid.UUID, session_id: uuid.UUID,
    ) -> None:
        """Bug 5 fix: generating flag must be cleared even on early exit."""
        repo.get_session.return_value = None

        with (
            patch("src.app.modules.ai.service._set_generating", return_value=True),
            patch(
                "src.app.modules.ai.service._clear_generating",
                new_callable=AsyncMock,
            ) as mock_clear_gen,
            patch(
                "src.app.modules.ai.service._clear_cancel",
                new_callable=AsyncMock,
            ) as mock_clear_cancel,
        ):
            async for _ in service.send_message(
                user_id, session_id, "Hello",
            ):
                pass

            mock_clear_gen.assert_called_once_with(session_id)
            mock_clear_cancel.assert_called_once_with(session_id)

    @pytest.mark.anyio()
    async def test_llm_timeout_yields_error(
        self, service: AIService, repo: AsyncMock, notes_repo: AsyncMock,
        user_id: uuid.UUID, session_id: uuid.UUID,
    ) -> None:
        """Bug 3: first-token timeout must yield ai:error with code llm_timeout."""
        from src.app.modules.ai.service import _LLMTimeoutError

        session = _mock_session(session_id=session_id, user_id=user_id)
        session.title = "Existing"
        repo.get_session.return_value = session
        repo.get_recent_messages.return_value = []
        repo.add_message.return_value = _mock_message()

        async def fake_stream(*args, **kwargs):
            await asyncio.sleep(100)
            yield "never"

        with (
            patch("src.app.modules.ai.service._set_generating", return_value=True),
            patch("src.app.modules.ai.service._clear_generating", new_callable=AsyncMock),
            patch("src.app.modules.ai.service._clear_cancel", new_callable=AsyncMock),
            patch("src.app.modules.ai.service.chat_completion_stream", side_effect=fake_stream),
            patch("src.app.modules.ai.service._stream_with_first_token_timeout") as mock_timeout,
            patch("src.app.modules.ai.service._token_budget", return_value=10000),
            patch("src.app.modules.ai.service._is_cancelled", return_value=False),
        ):
            # Simulate the timeout wrapper raising
            async def timeout_raises(*a, **kw):
                raise _LLMTimeoutError("timeout")
                yield  # noqa: unreachable

            mock_timeout.return_value = timeout_raises()

            events = []
            async for chunk in service.send_message(
                user_id, session_id, "Hello",
            ):
                events.append(chunk)

        assert any("llm_timeout" in e for e in events)
        assert any("ai:done" in e for e in events)


# =====================================================================
# cancel_generation
# =====================================================================


class TestCancelGeneration:
    @pytest.mark.anyio()
    async def test_success(
        self, service: AIService, repo: AsyncMock,
        user_id: uuid.UUID, session_id: uuid.UUID,
    ) -> None:
        repo.get_session.return_value = _mock_session(session_id=session_id)

        with patch("src.app.modules.ai.service.redis_client") as mock_redis:
            # generating key exists
            mock_redis.exists = AsyncMock(return_value=True)
            mock_redis.set = AsyncMock()

            result = await service.cancel_generation(user_id, session_id)

        assert result["status"] == "cancelled"

    @pytest.mark.anyio()
    async def test_session_not_found(
        self, service: AIService, repo: AsyncMock,
        user_id: uuid.UUID, session_id: uuid.UUID,
    ) -> None:
        repo.get_session.return_value = None

        with pytest.raises(NotFoundError):
            await service.cancel_generation(user_id, session_id)

    @pytest.mark.anyio()
    async def test_no_active_generation(
        self, service: AIService, repo: AsyncMock,
        user_id: uuid.UUID, session_id: uuid.UUID,
    ) -> None:
        repo.get_session.return_value = _mock_session(session_id=session_id)

        with patch("src.app.modules.ai.service.redis_client") as mock_redis:
            # generating key does not exist
            mock_redis.exists = AsyncMock(return_value=False)

            with pytest.raises(ConflictError, match="No active"):
                await service.cancel_generation(user_id, session_id)

    @pytest.mark.anyio()
    async def test_does_not_clear_generating_flag(
        self, service: AIService, repo: AsyncMock,
        user_id: uuid.UUID, session_id: uuid.UUID,
    ) -> None:
        """Fix 2: cancel_generation must NOT clear the generating flag.
        The generator's finally block handles cleanup."""
        repo.get_session.return_value = _mock_session(session_id=session_id)

        with patch("src.app.modules.ai.service.redis_client") as mock_redis:
            mock_redis.exists = AsyncMock(return_value=True)
            mock_redis.set = AsyncMock()
            mock_redis.delete = AsyncMock()

            await service.cancel_generation(user_id, session_id)

            # Should not have called delete on the generating key
            for call in mock_redis.delete.call_args_list:
                assert f"generating:{session_id}" not in str(call)


# =====================================================================
# update_action_status (proposals)
# =====================================================================


class TestUpdateActionStatus:
    @pytest.mark.anyio()
    async def test_apply_proposal(
        self, service: AIService, repo: AsyncMock,
        user_id: uuid.UUID, session_id: uuid.UUID,
    ) -> None:
        action_id = str(uuid.uuid4())
        actions = [
            {
                "type": "proposal",
                "id": action_id,
                "proposal_type": "edit_note",
                "status": "pending",
                "note_id": str(uuid.uuid4()),
                "data": {"title": "New"},
                "summary": None,
            },
        ]
        msg = _mock_message(
            session_id=session_id, role="assistant", actions=actions,
        )
        repo.get_session.return_value = _mock_session(session_id=session_id)
        repo.get_message.return_value = msg
        repo.update_message_actions.return_value = msg

        result = await service.update_action_status(
            user_id, session_id, msg.id, action_id, "applied",
        )

        assert actions[0]["status"] == "applied"
        assert actions[0]["data"] is None  # cleared after apply
        repo.update_message_actions.assert_called_once()

    @pytest.mark.anyio()
    async def test_dismiss_proposal(
        self, service: AIService, repo: AsyncMock,
        user_id: uuid.UUID, session_id: uuid.UUID,
    ) -> None:
        action_id = str(uuid.uuid4())
        actions = [
            {
                "type": "proposal",
                "id": action_id,
                "proposal_type": "create_note",
                "status": "pending",
                "note_id": None,
                "data": {"title": "Note"},
                "summary": None,
            },
        ]
        msg = _mock_message(session_id=session_id, actions=actions)
        repo.get_session.return_value = _mock_session(session_id=session_id)
        repo.get_message.return_value = msg
        repo.update_message_actions.return_value = msg

        await service.update_action_status(
            user_id, session_id, msg.id, action_id, "dismissed",
        )

        assert actions[0]["status"] == "dismissed"

    @pytest.mark.anyio()
    async def test_invalid_status(
        self, service: AIService, repo: AsyncMock,
        user_id: uuid.UUID, session_id: uuid.UUID,
    ) -> None:
        with pytest.raises(ValidationError, match="Status"):
            await service.update_action_status(
                user_id, session_id, uuid.uuid4(), "x", "invalid",
            )

    @pytest.mark.anyio()
    async def test_session_not_found(
        self, service: AIService, repo: AsyncMock,
        user_id: uuid.UUID, session_id: uuid.UUID,
    ) -> None:
        repo.get_session.return_value = None

        with pytest.raises(NotFoundError):
            await service.update_action_status(
                user_id, session_id, uuid.uuid4(), "x", "applied",
            )

    @pytest.mark.anyio()
    async def test_message_not_found(
        self, service: AIService, repo: AsyncMock,
        user_id: uuid.UUID, session_id: uuid.UUID,
    ) -> None:
        repo.get_session.return_value = _mock_session(session_id=session_id)
        repo.get_message.return_value = None

        with pytest.raises(NotFoundError, match="Assistant message"):
            await service.update_action_status(
                user_id, session_id, uuid.uuid4(), "x", "applied",
            )

    @pytest.mark.anyio()
    async def test_proposal_not_found(
        self, service: AIService, repo: AsyncMock,
        user_id: uuid.UUID, session_id: uuid.UUID,
    ) -> None:
        msg = _mock_message(
            session_id=session_id, actions=[{"type": "proposal", "id": "other"}],
        )
        repo.get_session.return_value = _mock_session(session_id=session_id)
        repo.get_message.return_value = msg

        with pytest.raises(NotFoundError, match="Proposal not found"):
            await service.update_action_status(
                user_id, session_id, msg.id, "nonexistent", "applied",
            )

    @pytest.mark.anyio()
    async def test_proposal_already_finalized(
        self, service: AIService, repo: AsyncMock,
        user_id: uuid.UUID, session_id: uuid.UUID,
    ) -> None:
        action_id = str(uuid.uuid4())
        actions = [
            {
                "type": "proposal",
                "id": action_id,
                "proposal_type": "edit_note",
                "status": "applied",
                "data": {},
            },
        ]
        msg = _mock_message(session_id=session_id, actions=actions)
        repo.get_session.return_value = _mock_session(session_id=session_id)
        repo.get_message.return_value = msg

        with pytest.raises(ConflictError, match="already finalized"):
            await service.update_action_status(
                user_id, session_id, msg.id, action_id, "applied",
            )

    @pytest.mark.anyio()
    async def test_no_actions_on_message(
        self, service: AIService, repo: AsyncMock,
        user_id: uuid.UUID, session_id: uuid.UUID,
    ) -> None:
        msg = _mock_message(session_id=session_id, actions=None)
        repo.get_session.return_value = _mock_session(session_id=session_id)
        repo.get_message.return_value = msg

        with pytest.raises(ValidationError, match="No actions"):
            await service.update_action_status(
                user_id, session_id, msg.id, "x", "applied",
            )


# =====================================================================
# pre_validate_confirm
# =====================================================================


class TestPreValidateConfirm:
    @pytest.mark.anyio()
    async def test_success(
        self, service: AIService, repo: AsyncMock,
        user_id: uuid.UUID, session_id: uuid.UUID,
    ) -> None:
        cid = str(uuid.uuid4())
        confirmation = {
            "type": "pending_confirmation",
            "id": cid,
            "status": "pending",
        }
        repo.get_session.return_value = _mock_session(session_id=session_id)
        repo.find_action_by_id.return_value = (_mock_message(), confirmation)

        result = await service.pre_validate_confirm(user_id, session_id, cid)

        assert result is None

    @pytest.mark.anyio()
    async def test_session_not_found(
        self, service: AIService, repo: AsyncMock,
        user_id: uuid.UUID, session_id: uuid.UUID,
    ) -> None:
        repo.get_session.return_value = None

        result = await service.pre_validate_confirm(
            user_id, session_id, "x",
        )

        assert result == (404, "Chat session not found")

    @pytest.mark.anyio()
    async def test_confirmation_not_found(
        self, service: AIService, repo: AsyncMock,
        user_id: uuid.UUID, session_id: uuid.UUID,
    ) -> None:
        repo.get_session.return_value = _mock_session(session_id=session_id)
        repo.find_action_by_id.return_value = (None, None)

        result = await service.pre_validate_confirm(
            user_id, session_id, "x",
        )

        assert result[0] == 404

    @pytest.mark.anyio()
    async def test_wrong_type(
        self, service: AIService, repo: AsyncMock,
        user_id: uuid.UUID, session_id: uuid.UUID,
    ) -> None:
        repo.get_session.return_value = _mock_session(session_id=session_id)
        repo.find_action_by_id.return_value = (
            _mock_message(),
            {"type": "proposal", "status": "pending"},
        )

        result = await service.pre_validate_confirm(
            user_id, session_id, "x",
        )

        assert result[0] == 404

    @pytest.mark.anyio()
    async def test_already_processed(
        self, service: AIService, repo: AsyncMock,
        user_id: uuid.UUID, session_id: uuid.UUID,
    ) -> None:
        repo.get_session.return_value = _mock_session(session_id=session_id)
        repo.find_action_by_id.return_value = (
            _mock_message(),
            {"type": "pending_confirmation", "status": "confirmed"},
        )

        result = await service.pre_validate_confirm(
            user_id, session_id, "x",
        )

        assert result[0] == 409


# =====================================================================
# confirm_bulk (SSE generator)
# =====================================================================


class TestConfirmBulk:
    @pytest.mark.anyio()
    async def test_conflict_when_generating(
        self, service: AIService, user_id: uuid.UUID, session_id: uuid.UUID,
    ) -> None:
        with patch("src.app.modules.ai.service._set_generating", return_value=False):
            events = []
            async for chunk in service.confirm_bulk(
                user_id, session_id, "cid",
            ):
                events.append(chunk)

        assert any("conflict" in e for e in events)
        assert any("ai:done" in e for e in events)

    @pytest.mark.anyio()
    async def test_confirmation_not_found_inside(
        self, service: AIService, repo: AsyncMock,
        user_id: uuid.UUID, session_id: uuid.UUID,
    ) -> None:
        repo.find_action_by_id.return_value = (None, None)

        with (
            patch("src.app.modules.ai.service._set_generating", return_value=True),
            patch("src.app.modules.ai.service._clear_generating", new_callable=AsyncMock),
            patch("src.app.modules.ai.service._clear_cancel", new_callable=AsyncMock),
        ):
            events = []
            async for chunk in service.confirm_bulk(
                user_id, session_id, "cid",
            ):
                events.append(chunk)

        assert any("not_found" in e for e in events)

    @pytest.mark.anyio()
    async def test_generating_flag_cleared(
        self, service: AIService, repo: AsyncMock,
        user_id: uuid.UUID, session_id: uuid.UUID,
    ) -> None:
        repo.find_action_by_id.return_value = (None, None)

        with (
            patch("src.app.modules.ai.service._set_generating", return_value=True),
            patch(
                "src.app.modules.ai.service._clear_generating",
                new_callable=AsyncMock,
            ) as mock_clear_gen,
            patch(
                "src.app.modules.ai.service._clear_cancel",
                new_callable=AsyncMock,
            ) as mock_clear_cancel,
        ):
            async for _ in service.confirm_bulk(
                user_id, session_id, "cid",
            ):
                pass

            mock_clear_gen.assert_called_once_with(session_id)
            mock_clear_cancel.assert_called_once_with(session_id)


# =====================================================================
# dismiss_bulk
# =====================================================================


class TestDismissBulk:
    @pytest.mark.anyio()
    async def test_success(
        self, service: AIService, repo: AsyncMock,
        user_id: uuid.UUID, session_id: uuid.UUID,
    ) -> None:
        cid = str(uuid.uuid4())
        confirmation = {
            "type": "pending_confirmation",
            "id": cid,
            "status": "pending",
            "operation_type": "add_tags",
            "note_ids": ["a"],
            "params": {},
            "summary": None,
        }
        msg = _mock_message(session_id=session_id, actions=[confirmation])
        repo.get_session.return_value = _mock_session(session_id=session_id)
        repo.find_action_by_id.return_value = (msg, confirmation)
        repo.update_message_actions.return_value = msg

        result = await service.dismiss_bulk(user_id, session_id, cid)

        assert confirmation["status"] == "dismissed"

    @pytest.mark.anyio()
    async def test_session_not_found(
        self, service: AIService, repo: AsyncMock,
        user_id: uuid.UUID, session_id: uuid.UUID,
    ) -> None:
        repo.get_session.return_value = None

        with pytest.raises(NotFoundError):
            await service.dismiss_bulk(user_id, session_id, "x")

    @pytest.mark.anyio()
    async def test_confirmation_not_found(
        self, service: AIService, repo: AsyncMock,
        user_id: uuid.UUID, session_id: uuid.UUID,
    ) -> None:
        repo.get_session.return_value = _mock_session(session_id=session_id)
        repo.find_action_by_id.return_value = (None, None)

        with pytest.raises(NotFoundError):
            await service.dismiss_bulk(user_id, session_id, "x")

    @pytest.mark.anyio()
    async def test_already_processed(
        self, service: AIService, repo: AsyncMock,
        user_id: uuid.UUID, session_id: uuid.UUID,
    ) -> None:
        confirmation = {
            "type": "pending_confirmation",
            "status": "confirmed",
        }
        repo.get_session.return_value = _mock_session(session_id=session_id)
        repo.find_action_by_id.return_value = (_mock_message(), confirmation)

        with pytest.raises(ConflictError, match="already processed"):
            await service.dismiss_bulk(user_id, session_id, "x")


# =====================================================================
# _clean_actions
# =====================================================================


class TestCleanActions:
    def test_removes_emitted_flag(self) -> None:
        actions = [
            {"type": "proposal", "id": "1", "_emitted": True},
            {"type": "proposal", "id": "2", "_emitted": True},
        ]
        result = AIService._clean_actions(actions)
        assert result is not None
        for a in result:
            assert "_emitted" not in a

    def test_empty_returns_none(self) -> None:
        assert AIService._clean_actions([]) is None

    def test_none_returns_none(self) -> None:
        assert AIService._clean_actions(None) is None
