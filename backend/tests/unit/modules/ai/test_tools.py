"""Unit tests for AI tools module — ToolExecutor, helpers, and deterministic generators."""

import json
import uuid
from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.modules.ai.tools import (
    BATCH_TOOL_NAMES,
    EXECUTOR_TOOLS,
    PLANNER_TOOLS,
    PROPOSE_TOOL_NAMES,
    READ_TOOL_NAMES,
    ToolExecutor,
    build_summary,
    generate_deterministic_proposals,
    make_pending_confirmation,
    make_proposal,
    truncate_at_word,
)

# --- Helpers ---


def _mock_note(
    note_id: uuid.UUID | None = None,
    user_id: uuid.UUID | None = None,
    title: str = "Test Note",
    content: str = "Some content",
    version: int = 1,
    tags: list[str] | None = None,
) -> MagicMock:
    n = MagicMock()
    n.id = note_id or uuid.uuid4()
    n.user_id = user_id or uuid.uuid4()
    n.title = title
    n.content = content
    n.version = version
    n.created_at = datetime.now(UTC)
    n.updated_at = datetime.now(UTC)
    n.deleted_at = None
    n.tags = tags or []
    return n


def _mock_tag(name: str = "tag") -> MagicMock:
    t = MagicMock()
    t.id = uuid.uuid4()
    t.name = name
    return t


# --- Fixtures ---


@pytest.fixture()
def user_id() -> uuid.UUID:
    return uuid.uuid4()


@pytest.fixture()
def actions() -> list[dict[str, Any]]:
    return []


@pytest.fixture()
def db() -> AsyncMock:
    return AsyncMock()


@pytest.fixture()
def executor(db: AsyncMock, user_id: uuid.UUID, actions: list[dict[str, Any]]) -> ToolExecutor:
    ex = ToolExecutor.__new__(ToolExecutor)
    ex.db = db
    ex.user_id = user_id
    ex.actions = actions
    ex.notes_repo = AsyncMock()
    ex.tags_repo = AsyncMock()
    ex.rag = AsyncMock()
    ex._proposal_keys = set()  # type: ignore
    ex._has_batch = False  # type: ignore
    return ex


# =====================================================================
# Tool schema constants
# =====================================================================


class TestToolSchemas:
    def test_planner_has_13_tools(self) -> None:
        assert len(PLANNER_TOOLS) == 13

    def test_executor_has_4_tools(self) -> None:
        assert len(EXECUTOR_TOOLS) == 4

    def test_tool_name_sets_correct(self) -> None:
        assert READ_TOOL_NAMES == {"search_notes", "get_note", "list_tags"}
        assert "batch_transform" in BATCH_TOOL_NAMES
        assert "propose_edit_note" in PROPOSE_TOOL_NAMES

    def test_all_tools_have_function_field(self) -> None:
        for tool in PLANNER_TOOLS + EXECUTOR_TOOLS:
            assert tool["type"] == "function"
            assert "name" in tool["function"]
            assert "parameters" in tool["function"]


# =====================================================================
# _truncate_at_word
# =====================================================================


class TestTruncateAtWord:
    def test_short_text_unchanged(self) -> None:
        assert truncate_at_word("hello", 100) == "hello"

    def test_exact_length_unchanged(self) -> None:
        text = "x" * 100
        assert truncate_at_word(text, 100) == text

    def test_truncates_at_word_boundary(self) -> None:
        text = "hello world this is a long text"
        result = truncate_at_word(text, 15)
        assert result.endswith("…")
        assert len(result) <= 16  # 15 + ellipsis
        assert "hello world" in result

    def test_no_space_keeps_hard_cut(self) -> None:
        text = "a" * 200
        result = truncate_at_word(text, 100)
        assert result.endswith("…")
        assert len(result) == 101  # 100 chars + ellipsis

    def test_empty_string(self) -> None:
        assert truncate_at_word("", 100) == ""

    def test_space_too_early_falls_back_to_hard_cut(self) -> None:
        """If the last space is before the midpoint, do a hard cut."""
        text = "ab " + "x" * 200
        result = truncate_at_word(text, 100)
        assert result.endswith("…")
        assert len(result) == 101


# =====================================================================
# make_proposal / make_pending_confirmation
# =====================================================================


class TestMakeProposal:
    def test_creates_pending_proposal(self) -> None:
        p = make_proposal("edit_note", "some-uuid", {"title": "New"})
        assert p["type"] == "proposal"
        assert p["status"] == "pending"
        assert p["proposal_type"] == "edit_note"
        assert p["note_id"] == "some-uuid"
        assert p["data"] == {"title": "New"}
        assert p["id"]  # UUID string

    def test_create_note_has_none_note_id(self) -> None:
        p = make_proposal("create_note", None, {"title": "X"})
        assert p["note_id"] is None


class TestMakePendingConfirmation:
    def test_creates_pending(self) -> None:
        pc = make_pending_confirmation(
            "add_tags", ["id1", "id2"], {"tags": ["work"]},
        )
        assert pc["type"] == "pending_confirmation"
        assert pc["status"] == "pending"
        assert pc["operation_type"] == "add_tags"
        assert pc["note_ids"] == ["id1", "id2"]
        assert pc["params"]["tags"] == ["work"]


# =====================================================================
# build_summary
# =====================================================================


class TestBuildSummary:
    def test_edit_note_applied(self) -> None:
        action: dict[str, Any] = {
            "type": "proposal",
            "proposal_type": "edit_note",
            "data": {"title": "Моя заметка"},
        }
        s = build_summary(action, "applied")
        assert "Моя заметка" in s

    def test_edit_note_dismissed(self) -> None:
        action: dict[str, Any] = {
            "type": "proposal",
            "proposal_type": "edit_note",
            "data": {"title": "Тест"},
        }
        s = build_summary(action, "dismissed")
        assert "Тест" in s

    def test_create_note_applied(self) -> None:
        action: dict[str, Any] = {
            "type": "proposal",
            "proposal_type": "create_note",
            "data": {"title": "New"},
        }
        s = build_summary(action, "applied")
        assert "New" in s

    def test_delete_note_applied(self) -> None:
        action: dict[str, Any] = {
            "type": "proposal",
            "proposal_type": "delete_note",
            "data": {"note_title": "Old"},
        }
        s = build_summary(action, "applied")
        assert "Old" in s

    def test_add_tags_applied(self) -> None:
        action: dict[str, Any] = {
            "type": "proposal",
            "proposal_type": "add_tags",
            "data": {"tags": ["work", "urgent"], "title": "Note"},
        }
        s = build_summary(action, "applied")
        assert "work" in s

    def test_remove_tags_dismissed(self) -> None:
        action: dict[str, Any] = {
            "type": "proposal",
            "proposal_type": "remove_tags",
            "data": {"title": "Note"},
        }
        s = build_summary(action, "dismissed")
        assert "Note" in s

    def test_pending_confirmation_dismissed(self) -> None:
        action: dict[str, Any] = {
            "type": "pending_confirmation",
            "operation_type": "delete",
            "note_ids": ["a", "b"],
        }
        s = build_summary(action, "dismissed")
        assert "delete" in s
        assert "2" in s

    def test_pending_confirmation_confirmed(self) -> None:
        action: dict[str, Any] = {
            "type": "pending_confirmation",
            "operation_type": "add_tags",
            "note_ids": ["a"],
        }
        s = build_summary(action, "confirmed")
        assert "add_tags" in s

    def test_unknown_type(self) -> None:
        action = {"type": "unknown"}
        s = build_summary(action, "applied")
        assert "unknown" in s

    def test_unknown_proposal_type(self) -> None:
        action: dict[str, Any] = {
            "type": "proposal",
            "proposal_type": "magic",
            "data": {},
        }
        s = build_summary(action, "applied")
        assert "magic" in s


# =====================================================================
# ToolExecutor.execute — dispatch
# =====================================================================


class TestExecuteDispatch:
    @pytest.mark.anyio()
    async def test_invalid_json(self, executor: ToolExecutor) -> None:
        result = json.loads(await executor.execute("search_notes", "not json"))
        assert result["error"] == "invalid_json"

    @pytest.mark.anyio()
    async def test_unknown_tool(self, executor: ToolExecutor) -> None:
        result = json.loads(await executor.execute("nonexistent", "{}"))
        assert result["error"] == "unknown_tool"

    @pytest.mark.anyio()
    async def test_tool_error_caught(self, executor: ToolExecutor) -> None:
        executor.notes_repo.get_active_note.side_effect = RuntimeError("boom")  # type: ignore
        result = json.loads(
            await executor.execute("get_note", json.dumps({"note_id": str(uuid.uuid4())})),
        )
        assert result["error"] == "tool_error"


# =====================================================================
# search_notes
# =====================================================================


class TestSearchNotes:
    @pytest.mark.anyio()
    async def test_relevance_without_query_fails(self, executor: ToolExecutor) -> None:
        result = json.loads(
            await executor.execute(
                "search_notes",
                json.dumps({"sort_by": "relevance"}),
            ),
        )
        assert result["error"] == "validation_error"

    @pytest.mark.anyio()
    async def test_query_without_mode_fails(self, executor: ToolExecutor) -> None:
        result = json.loads(
            await executor.execute(
                "search_notes",
                json.dumps({"query": "test"}),
            ),
        )
        assert result["error"] == "validation_error"

    @pytest.mark.anyio()
    async def test_fulltext_search(self, executor: ToolExecutor) -> None:
        note = _mock_note()
        executor.notes_repo.list_notes.return_value = ([note], 1)  # type: ignore
        executor.tags_repo.get_tags_by_names.return_value = []  # type: ignore

        result = json.loads(
            await executor.execute(
                "search_notes",
                json.dumps({"query": "test", "search_mode": "fulltext", "limit": 3}),
            ),
        )

        assert result["total_count"] == 1
        assert len(result["notes"]) == 1
        assert result["notes"][0]["note_id"] == str(note.id)

    @pytest.mark.anyio()
    async def test_semantic_search(self, executor: ToolExecutor) -> None:
        note = _mock_note()
        search_result = MagicMock()
        search_result.results = [MagicMock(note_id=note.id, score=0.95)]
        executor.rag.search.return_value = search_result  # type: ignore
        executor.notes_repo.get_active_notes_by_ids.return_value = [note]  # type: ignore

        result = json.loads(
            await executor.execute(
                "search_notes",
                json.dumps({"query": "test", "search_mode": "semantic"}),
            ),
        )

        assert len(result["notes"]) == 1
        assert result["notes"][0]["relevance_score"] == 0.95
        executor.notes_repo.get_active_notes_by_ids.assert_called_once()  # type: ignore

    @pytest.mark.anyio()
    async def test_semantic_search_empty(self, executor: ToolExecutor) -> None:
        search_result = MagicMock()
        search_result.results = []
        executor.rag.search.return_value = search_result  # type: ignore

        result = json.loads(
            await executor.execute(
                "search_notes",
                json.dumps({"query": "nothing", "search_mode": "semantic"}),
            ),
        )

        assert result["total_count"] == 0
        assert result["notes"] == []

    @pytest.mark.anyio()
    async def test_no_filters_lists_notes(self, executor: ToolExecutor) -> None:
        executor.notes_repo.list_notes.return_value = ([], 0)  # type: ignore
        executor.tags_repo.get_tags_by_names.return_value = []  # type: ignore

        result = json.loads(
            await executor.execute("search_notes", json.dumps({})),
        )

        assert result["total_count"] == 0

    @pytest.mark.anyio()
    async def test_exclude_tags_passed_to_repo(self, executor: ToolExecutor) -> None:
        """exclude_tags are resolved and passed to list_notes as exclude_tag_ids."""
        tag = _mock_tag("archive")
        executor.tags_repo.get_tags_by_names.return_value = [tag]  # type: ignore
        executor.notes_repo.list_notes.return_value = ([], 0)  # type: ignore

        await executor.execute(
            "search_notes",
            json.dumps({"exclude_tags": ["archive"]}),
        )

        # Verify exclude_tag_ids was passed to list_notes
        call_kwargs = executor.notes_repo.list_notes.call_args  # type: ignore
        assert call_kwargs.kwargs.get("exclude_tag_ids") == [tag.id]  # type: ignore

    @pytest.mark.anyio()
    async def test_date_filters_passed_to_repo(self, executor: ToolExecutor) -> None:
        """Date filters are parsed and passed to list_notes."""
        executor.tags_repo.get_tags_by_names.return_value = []  # type: ignore
        executor.notes_repo.list_notes.return_value = ([], 0)  # type: ignore

        await executor.execute(
            "search_notes",
            json.dumps({"created_from": "2025-01-01T00:00:00+00:00"}),
        )

        call_kwargs = executor.notes_repo.list_notes.call_args  # type: ignore
        assert "created_from" in call_kwargs.kwargs  # type: ignore
        assert call_kwargs.kwargs["created_from"] is not None  # type: ignore


# =====================================================================
# get_note
# =====================================================================


class TestGetNote:
    @pytest.mark.anyio()
    async def test_success(self, executor: ToolExecutor) -> None:
        note = _mock_note(title="Hello", content="World")
        executor.notes_repo.get_active_note.return_value = note  # type: ignore

        result = json.loads(
            await executor.execute(
                "get_note",
                json.dumps({"note_id": str(note.id)}),
            ),
        )

        assert result["title"] == "Hello"
        assert result["content"] == "World"

    @pytest.mark.anyio()
    async def test_not_found(self, executor: ToolExecutor) -> None:
        executor.notes_repo.get_active_note.return_value = None  # type: ignore

        result = json.loads(
            await executor.execute(
                "get_note",
                json.dumps({"note_id": str(uuid.uuid4())}),
            ),
        )

        assert result["error"] == "note_not_found"

    @pytest.mark.anyio()
    async def test_invalid_uuid(self, executor: ToolExecutor) -> None:
        result = json.loads(
            await executor.execute(
                "get_note",
                json.dumps({"note_id": "not-a-uuid"}),
            ),
        )

        assert result["error"] == "validation_error"


# =====================================================================
# list_tags
# =====================================================================


class TestListTags:
    @pytest.mark.anyio()
    async def test_returns_tags(self, executor: ToolExecutor) -> None:
        tags = [_mock_tag("work"), _mock_tag("personal")]
        for tg in tags:
            tg.notes = [MagicMock()]
        executor.tags_repo.list_tags.return_value = (tags, 2)  # type: ignore

        result = json.loads(
            await executor.execute("list_tags", "{}"),
        )

        assert len(result) == 2
        assert result[0]["name"] == "work"


# =====================================================================
# Propose tools
# =====================================================================


class TestProposeEditNote:
    @pytest.mark.anyio()
    async def test_success(
        self, executor: ToolExecutor, actions: list[dict[str, Any]],
    ) -> None:
        note = _mock_note()
        executor.notes_repo.get_active_note.return_value = note  # type: ignore

        result = json.loads(
            await executor.execute(
                "propose_edit_note",
                json.dumps({
                    "note_id": str(note.id),
                    "title": "New Title",
                }),
            ),
        )

        assert result["status"] == "registered"
        assert len(actions) == 1
        assert actions[0]["proposal_type"] == "edit_note"

    @pytest.mark.anyio()
    async def test_no_title_or_content(self, executor: ToolExecutor) -> None:
        result = json.loads(
            await executor.execute(
                "propose_edit_note",
                json.dumps({"note_id": str(uuid.uuid4())}),
            ),
        )
        assert result["error"] == "validation_error"

    @pytest.mark.anyio()
    async def test_note_not_found(self, executor: ToolExecutor) -> None:
        executor.notes_repo.get_active_note.return_value = None  # type: ignore

        result = json.loads(
            await executor.execute(
                "propose_edit_note",
                json.dumps({"note_id": str(uuid.uuid4()), "title": "X"}),
            ),
        )

        assert result["error"] == "note_not_found"

    @pytest.mark.anyio()
    async def test_duplicate_proposal(
        self, executor: ToolExecutor, actions: list[dict[str, Any]],
    ) -> None:
        note = _mock_note()
        executor.notes_repo.get_active_note.return_value = note  # type: ignore

        await executor.execute(
            "propose_edit_note",
            json.dumps({"note_id": str(note.id), "title": "A"}),
        )
        result = json.loads(
            await executor.execute(
                "propose_edit_note",
                json.dumps({"note_id": str(note.id), "title": "B"}),
            ),
        )

        assert result["error"] == "duplicate_proposal"
        assert len(actions) == 1


class TestProposeCreateNote:
    @pytest.mark.anyio()
    async def test_success(
        self, executor: ToolExecutor, actions: list[dict[str, Any]],
    ) -> None:
        result = json.loads(
            await executor.execute(
                "propose_create_note",
                json.dumps({"title": "New Note", "content": "Body"}),
            ),
        )

        assert result["status"] == "registered"
        assert len(actions) == 1
        assert actions[0]["proposal_type"] == "create_note"
        assert actions[0]["note_id"] is None

    @pytest.mark.anyio()
    async def test_too_many_tags(self, executor: ToolExecutor) -> None:
        with patch("app.modules.ai.tools.settings") as mock_s:
            mock_s.max_tags_per_note = 10
            result = json.loads(
                await executor.execute(
                    "propose_create_note",
                    json.dumps({"title": "X", "tags": [f"t{i}" for i in range(15)]}),
                ),
            )

        assert result["error"] == "validation_error"


class TestProposeDeleteNote:
    @pytest.mark.anyio()
    async def test_success(
        self, executor: ToolExecutor, actions: list[dict[str, Any]],
    ) -> None:
        note = _mock_note(title="To Delete")
        executor.notes_repo.get_active_note.return_value = note  # type: ignore

        result = json.loads(
            await executor.execute(
                "propose_delete_note",
                json.dumps({"note_id": str(note.id)}),
            ),
        )

        assert result["status"] == "registered"
        assert actions[0]["data"]["note_title"] == "To Delete"


class TestProposeAddTags:
    @pytest.mark.anyio()
    async def test_success(
        self, executor: ToolExecutor, actions: list[dict[str, Any]],
    ) -> None:
        note = _mock_note()
        executor.notes_repo.get_active_note.return_value = note  # type: ignore

        result = json.loads(
            await executor.execute(
                "propose_add_tags",
                json.dumps({"note_id": str(note.id), "tags": ["work"]}),
            ),
        )

        assert result["status"] == "registered"
        assert actions[0]["data"]["tags"] == ["work"]

    @pytest.mark.anyio()
    async def test_empty_tags(self, executor: ToolExecutor) -> None:
        result = json.loads(
            await executor.execute(
                "propose_add_tags",
                json.dumps({"note_id": str(uuid.uuid4()), "tags": []}),
            ),
        )
        assert result["error"] == "validation_error"

    @pytest.mark.anyio()
    async def test_exceeds_tag_limit(
        self, executor: ToolExecutor,
    ) -> None:
        note = _mock_note(tags=[_mock_tag(f"t{i}") for i in range(9)])
        executor.notes_repo.get_active_note.return_value = note  # type: ignore

        with patch("app.modules.ai.tools.settings") as mock_s:
            mock_s.max_tags_per_note = 10
            result = json.loads(
                await executor.execute(
                    "propose_add_tags",
                    json.dumps({
                        "note_id": str(note.id),
                        "tags": ["extra1", "extra2"],
                    }),
                ),
            )

        assert result["error"] == "validation_error"
        assert "limit" in result["details"].lower()


class TestProposeRemoveTags:
    @pytest.mark.anyio()
    async def test_success(
        self, executor: ToolExecutor, actions: list[dict[str, Any]],
    ) -> None:
        note = _mock_note(tags=[_mock_tag("work")])
        executor.notes_repo.get_active_note.return_value = note  # type: ignore

        result = json.loads(
            await executor.execute(
                "propose_remove_tags",
                json.dumps({"note_id": str(note.id), "tags": ["work"]}),
            ),
        )

        assert result["status"] == "registered"


# =====================================================================
# Batch tools
# =====================================================================


class TestBatchTools:
    @pytest.mark.anyio()
    async def test_batch_add_tags(
        self, executor: ToolExecutor, actions: list[dict[str, Any]], user_id: uuid.UUID,
    ) -> None:
        nid = uuid.uuid4()
        note = _mock_note(note_id=nid, user_id=user_id)
        executor.notes_repo.get_active_notes_by_ids.return_value = [note]  # type: ignore

        result = json.loads(
            await executor.execute(
                "batch_add_tags",
                json.dumps({"note_ids": [str(nid)], "tags": ["work"]}),
            ),
        )

        assert result["status"] == "awaiting_confirmation"
        assert len(actions) == 1
        assert actions[0]["type"] == "pending_confirmation"

    @pytest.mark.anyio()
    async def test_batch_delete(
        self, executor: ToolExecutor, actions: list[dict[str, Any]], user_id: uuid.UUID,
    ) -> None:
        nid = uuid.uuid4()
        executor.notes_repo.get_active_notes_by_ids.return_value = [  # type: ignore
            _mock_note(note_id=nid),
        ]

        result = json.loads(
            await executor.execute(
                "batch_delete",
                json.dumps({"note_ids": [str(nid)]}),
            ),
        )

        assert result["status"] == "awaiting_confirmation"
        assert actions[0]["operation_type"] == "delete"

    @pytest.mark.anyio()
    async def test_one_batch_limit(
        self, executor: ToolExecutor, user_id: uuid.UUID,
    ) -> None:
        nid = uuid.uuid4()
        executor.notes_repo.get_active_notes_by_ids.return_value = [  # type: ignore
            _mock_note(note_id=nid),
        ]

        await executor.execute(
            "batch_add_tags",
            json.dumps({"note_ids": [str(nid)], "tags": ["a"]}),
        )

        # Second batch should fail
        result = json.loads(
            await executor.execute(
                "batch_delete",
                json.dumps({"note_ids": [str(nid)]}),
            ),
        )

        assert result["error"] == "validation_error"
        assert "one batch" in result["details"].lower()

    @pytest.mark.anyio()
    async def test_too_many_notes(self, executor: ToolExecutor) -> None:
        with patch("app.modules.ai.tools.settings") as mock_s:
            mock_s.max_notes_in_bulk = 25
            ids = [str(uuid.uuid4()) for _ in range(30)]
            result = json.loads(
                await executor.execute(
                    "batch_delete",
                    json.dumps({"note_ids": ids}),
                ),
            )

        assert result["error"] == "too_many_notes"

    @pytest.mark.anyio()
    async def test_no_valid_notes(self, executor: ToolExecutor) -> None:
        executor.notes_repo.get_active_notes_by_ids.return_value = []  # type: ignore

        with patch("app.modules.ai.tools.settings") as mock_s:
            mock_s.max_notes_in_bulk = 25
            result = json.loads(
                await executor.execute(
                    "batch_delete",
                    json.dumps({"note_ids": [str(uuid.uuid4())]}),
                ),
            )

        assert result["error"] == "no_valid_notes"

    @pytest.mark.anyio()
    async def test_excluded_notes_reported(
        self, executor: ToolExecutor,
    ) -> None:
        nid_valid = uuid.uuid4()
        nid_invalid = uuid.uuid4()

        executor.notes_repo.get_active_notes_by_ids.return_value = [  # type: ignore
            _mock_note(note_id=nid_valid),
        ]

        with patch("app.modules.ai.tools.settings") as mock_s:
            mock_s.max_notes_in_bulk = 25
            result = json.loads(
                await executor.execute(
                    "batch_delete",
                    json.dumps({
                        "note_ids": [str(nid_valid), str(nid_invalid)],
                    }),
                ),
            )

        assert result["valid_note_count"] == 1
        assert str(nid_invalid) in result["excluded_note_ids"]


class TestBatchReplace:
    @pytest.mark.anyio()
    async def test_success(
        self, executor: ToolExecutor, actions: list[dict[str, Any]],
    ) -> None:
        nid = uuid.uuid4()
        executor.notes_repo.get_active_notes_by_ids.return_value = [  # type: ignore
            _mock_note(note_id=nid),
        ]

        with patch("app.modules.ai.tools.settings") as mock_s:
            mock_s.max_notes_in_bulk = 25
            result = json.loads(
                await executor.execute(
                    "batch_replace",
                    json.dumps({
                        "note_ids": [str(nid)],
                        "pattern": "foo",
                        "replacement": "bar",
                    }),
                ),
            )

        assert result["status"] == "awaiting_confirmation"
        assert actions[0]["params"]["pattern"] == "foo"

    @pytest.mark.anyio()
    async def test_invalid_regex(self, executor: ToolExecutor) -> None:
        result = json.loads(
            await executor.execute(
                "batch_replace",
                json.dumps({
                    "note_ids": [str(uuid.uuid4())],
                    "pattern": "[invalid",
                    "replacement": "x",
                }),
            ),
        )

        assert "error" in result


class TestBatchTransform:
    @pytest.mark.anyio()
    async def test_success(
        self, executor: ToolExecutor, actions: list[dict[str, Any]],
    ) -> None:
        nid = uuid.uuid4()
        executor.notes_repo.get_active_notes_by_ids.return_value = [  # type: ignore
            _mock_note(note_id=nid),
        ]

        with patch("app.modules.ai.tools.settings") as mock_s:
            mock_s.max_notes_in_bulk = 25
            result = json.loads(
                await executor.execute(
                    "batch_transform",
                    json.dumps({
                        "note_ids": [str(nid)],
                        "instruction": "Translate to English",
                    }),
                ),
            )

        assert result["status"] == "awaiting_confirmation"
        assert actions[0]["params"]["instruction"] == "Translate to English"

    @pytest.mark.anyio()
    async def test_empty_instruction(self, executor: ToolExecutor) -> None:
        result = json.loads(
            await executor.execute(
                "batch_transform",
                json.dumps({
                    "note_ids": [str(uuid.uuid4())],
                    "instruction": "",
                }),
            ),
        )

        assert result["error"] == "validation_error"


# =====================================================================
# generate_deterministic_proposals
# =====================================================================


class TestGenerateDeterministicProposals:
    @pytest.mark.anyio()
    async def test_add_tags(self, db: AsyncMock, user_id: uuid.UUID) -> None:
        nid = uuid.uuid4()
        note = _mock_note(note_id=nid, user_id=user_id)
        confirmation: dict[str, Any] = {
            "operation_type": "add_tags",
            "note_ids": [str(nid)],
            "params": {"tags": ["work"]},
        }

        with patch("app.modules.ai.tools.NotesRepository") as mock_repo:
            mock_repo.return_value.get_active_note = AsyncMock(return_value=note)
            result = await generate_deterministic_proposals(
                db, user_id, confirmation,
            )

        assert len(result) == 1
        assert result[0]["proposal_type"] == "add_tags"
        assert result[0]["data"]["tags"] == ["work"]

    @pytest.mark.anyio()
    async def test_remove_tags(self, db: AsyncMock, user_id: uuid.UUID) -> None:
        nid = uuid.uuid4()
        note = _mock_note(note_id=nid)
        confirmation: dict[str, Any] = {
            "operation_type": "remove_tags",
            "note_ids": [str(nid)],
            "params": {"tags": ["old"]},
        }

        with patch("app.modules.ai.tools.NotesRepository") as mock_repo:
            mock_repo.return_value.get_active_note = AsyncMock(return_value=note)
            result = await generate_deterministic_proposals(
                db, user_id, confirmation,
            )

        assert len(result) == 1
        assert result[0]["proposal_type"] == "remove_tags"

    @pytest.mark.anyio()
    async def test_delete(self, db: AsyncMock, user_id: uuid.UUID) -> None:
        nid = uuid.uuid4()
        note = _mock_note(note_id=nid, title="My Note")
        confirmation: dict[str, Any] = {
            "operation_type": "delete",
            "note_ids": [str(nid)],
            "params": {},
        }

        with patch("app.modules.ai.tools.NotesRepository") as mock_repo:
            mock_repo.return_value.get_active_note = AsyncMock(return_value=note)
            result = await generate_deterministic_proposals(
                db, user_id, confirmation,
            )

        assert len(result) == 1
        assert result[0]["proposal_type"] == "delete_note"
        assert result[0]["data"]["note_title"] == "My Note"

    @pytest.mark.anyio()
    async def test_replace_content(self, db: AsyncMock, user_id: uuid.UUID) -> None:
        nid = uuid.uuid4()
        note = _mock_note(note_id=nid, content="hello world")
        confirmation: dict[str, Any] = {
            "operation_type": "replace",
            "note_ids": [str(nid)],
            "params": {
                "pattern": "hello",
                "replacement": "Hi",
                "flags": [],
                "scope": "content",
            },
        }

        with patch("app.modules.ai.tools.NotesRepository") as mock_repo:
            mock_repo.return_value.get_active_note = AsyncMock(return_value=note)
            result = await generate_deterministic_proposals(
                db, user_id, confirmation,
            )

        assert len(result) == 1
        assert result[0]["data"]["content"] == "Hi world"

    @pytest.mark.anyio()
    async def test_replace_no_match(self, db: AsyncMock, user_id: uuid.UUID) -> None:
        nid = uuid.uuid4()
        note = _mock_note(note_id=nid, content="no match here")
        confirmation: dict[str, Any] = {
            "operation_type": "replace",
            "note_ids": [str(nid)],
            "params": {
                "pattern": "xyz",
                "replacement": "abc",
                "flags": [],
                "scope": "content",
            },
        }

        with patch("app.modules.ai.tools.NotesRepository") as mock_repo:
            mock_repo.return_value.get_active_note = AsyncMock(return_value=note)
            result = await generate_deterministic_proposals(
                db, user_id, confirmation,
            )

        assert len(result) == 0  # no change = no proposal

    @pytest.mark.anyio()
    async def test_replace_title_scope(self, db: AsyncMock, user_id: uuid.UUID) -> None:
        nid = uuid.uuid4()
        note = _mock_note(note_id=nid, title="Old Title", content="Content")
        confirmation: dict[str, Any] = {
            "operation_type": "replace",
            "note_ids": [str(nid)],
            "params": {
                "pattern": "Old",
                "replacement": "New",
                "flags": [],
                "scope": "title",
            },
        }

        with patch("app.modules.ai.tools.NotesRepository") as mock_repo:
            mock_repo.return_value.get_active_note = AsyncMock(return_value=note)
            result = await generate_deterministic_proposals(
                db, user_id, confirmation,
            )

        assert len(result) == 1
        assert result[0]["data"]["title"] == "New Title"
        assert "content" not in result[0]["data"]

    @pytest.mark.anyio()
    async def test_replace_case_insensitive(
        self, db: AsyncMock, user_id: uuid.UUID,
    ) -> None:
        nid = uuid.uuid4()
        note = _mock_note(note_id=nid, content="Hello HELLO hello")
        confirmation: dict[str, Any] = {
            "operation_type": "replace",
            "note_ids": [str(nid)],
            "params": {
                "pattern": "hello",
                "replacement": "hi",
                "flags": ["i"],
                "scope": "content",
            },
        }

        with patch("app.modules.ai.tools.NotesRepository") as mock_repo:
            mock_repo.return_value.get_active_note = AsyncMock(return_value=note)
            result = await generate_deterministic_proposals(
                db, user_id, confirmation,
            )

        assert len(result) == 1
        assert result[0]["data"]["content"] == "hi hi hi"

    @pytest.mark.anyio()
    async def test_skips_invalid_uuid(self, db: AsyncMock, user_id: uuid.UUID) -> None:
        confirmation: dict[str, Any] = {
            "operation_type": "delete",
            "note_ids": ["not-a-uuid"],
            "params": {},
        }

        with patch("app.modules.ai.tools.NotesRepository") as mock_repo:
            mock_repo.return_value.get_active_note = AsyncMock()
            result = await generate_deterministic_proposals(
                db, user_id, confirmation,
            )

        assert len(result) == 0

    @pytest.mark.anyio()
    async def test_skips_missing_notes(self, db: AsyncMock, user_id: uuid.UUID) -> None:
        confirmation: dict[str, Any] = {
            "operation_type": "delete",
            "note_ids": [str(uuid.uuid4())],
            "params": {},
        }

        with patch("app.modules.ai.tools.NotesRepository") as mock_repo:
            mock_repo.return_value.get_active_note = AsyncMock(return_value=None)
            result = await generate_deterministic_proposals(
                db, user_id, confirmation,
            )

        assert len(result) == 0


# =====================================================================
# _parse_date_filters
# =====================================================================


class TestParseDateFilters:
    def test_parses_valid_dates(self) -> None:
        result = ToolExecutor._parse_date_filters({  # type: ignore
            "created_from": "2025-01-01T00:00:00+00:00",
            "updated_to": "2025-12-31T23:59:59+00:00",
        })
        assert "created_from" in result
        assert "updated_to" in result
        assert isinstance(result["created_from"], datetime)

    def test_invalid_date_ignored(self) -> None:
        result = ToolExecutor._parse_date_filters({  # type: ignore
            "created_from": "not-a-date",
        })
        assert "created_from" not in result

    def test_empty_args(self) -> None:
        result = ToolExecutor._parse_date_filters({})  # type: ignore
        assert result == {}

    def test_missing_fields_skipped(self) -> None:
        result = ToolExecutor._parse_date_filters({  # type: ignore
            "some_other_field": "value",
        })
        assert result == {}


# =====================================================================
# Static helper methods
# =====================================================================


class TestParseUuid:
    def test_valid(self) -> None:
        uid = uuid.uuid4()
        assert ToolExecutor._parse_uuid(str(uid)) == uid  # type: ignore

    def test_invalid(self) -> None:
        assert ToolExecutor._parse_uuid("bad") is None  # type: ignore

    def test_none(self) -> None:
        assert ToolExecutor._parse_uuid(None) is None  # type: ignore
