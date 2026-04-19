"""Unit tests for NotesService."""

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.app.common.exceptions import ConflictError, NotFoundError, ValidationError
from src.app.modules.notes.service import NotesService

# --- Helpers ---


def _mock_tag(tag_id: uuid.UUID | None = None, name: str = "tag") -> MagicMock:
    t = MagicMock()
    t.id = tag_id or uuid.uuid4()
    t.name = name
    return t


def _mock_note(
    note_id: uuid.UUID | None = None,
    user_id: uuid.UUID | None = None,
    title: str | None = "Test Note",
    content: str | None = "Some content",
    version: int = 1,
    deleted_at: datetime | None = None,
    tags: list[MagicMock] | None = None,
) -> MagicMock:
    n = MagicMock()
    n.id = note_id or uuid.uuid4()
    n.user_id = user_id or uuid.uuid4()
    n.title = title
    n.content = content
    n.version = version
    n.created_at = datetime.now(UTC)
    n.updated_at = datetime.now(UTC)
    n.deleted_at = deleted_at
    n.tags = tags or []
    return n


# --- Fixtures ---


@pytest.fixture()
def repo() -> AsyncMock:
    return AsyncMock()


@pytest.fixture()
def tags_repo() -> AsyncMock:
    return AsyncMock()


@pytest.fixture()
def rag() -> AsyncMock:
    return AsyncMock()


@pytest.fixture()
def service(repo: AsyncMock, tags_repo: AsyncMock, rag: AsyncMock) -> NotesService:
    svc = NotesService.__new__(NotesService)
    svc.repo = repo
    svc.tags_repo = tags_repo
    svc.rag = rag
    return svc


@pytest.fixture()
def user_id() -> uuid.UUID:
    return uuid.uuid4()


# --- create ---


class TestCreate:
    @pytest.mark.anyio()
    async def test_success(
        self,
        service: NotesService,
        repo: AsyncMock,
        rag: AsyncMock,
        user_id: uuid.UUID,
    ) -> None:
        repo.count_user_notes.return_value = 0
        created = created = _mock_note(user_id=user_id, title="Title", content="Content")
        repo.create_note.return_value = created
        repo.get_active_note.return_value = created

        result = await service.create(user_id, "Title", "Content", [])

        repo.create_note.assert_called_once()
        rag.index_note.assert_called_once()
        assert result.title == "Title"

    @pytest.mark.anyio()
    async def test_with_tags(
        self,
        service: NotesService,
        repo: AsyncMock,
        tags_repo: AsyncMock,
        user_id: uuid.UUID,
    ) -> None:
        repo.count_user_notes.return_value = 0
        tag_id = uuid.uuid4()
        tags_repo.verify_tags_belong_to_user.return_value = [tag_id]

        note = _mock_note(user_id=user_id, tags=[_mock_tag(tag_id, "work")])
        repo.create_note.return_value = note
        repo.get_active_note.return_value = note

        result = await service.create(user_id, "Title", "Content", [tag_id])

        repo.set_note_tags.assert_called_once_with(note.id, [tag_id])
        assert len(result.tags) == 1

    @pytest.mark.anyio()
    async def test_note_limit_reached(
        self,
        service: NotesService,
        repo: AsyncMock,
        user_id: uuid.UUID,
    ) -> None:
        repo.count_user_notes.return_value = 3000

        with pytest.raises(ConflictError, match="limit"):
            await service.create(user_id, "Title", "Content", [])

    @pytest.mark.anyio()
    async def test_too_many_tags(
        self,
        service: NotesService,
        repo: AsyncMock,
        user_id: uuid.UUID,
    ) -> None:
        repo.count_user_notes.return_value = 0
        tag_ids = [uuid.uuid4() for _ in range(11)]

        with pytest.raises(ValidationError, match="tags"):
            await service.create(user_id, "Title", "Content", tag_ids)

    @pytest.mark.anyio()
    async def test_tags_not_found(
        self,
        service: NotesService,
        repo: AsyncMock,
        tags_repo: AsyncMock,
        user_id: uuid.UUID,
    ) -> None:
        repo.count_user_notes.return_value = 0
        tag_ids = [uuid.uuid4(), uuid.uuid4()]
        tags_repo.verify_tags_belong_to_user.return_value = [tag_ids[0]]  # only 1 found

        with pytest.raises(NotFoundError, match="tags not found"):
            await service.create(user_id, "Title", "Content", tag_ids)


# --- get ---


class TestGet:
    @pytest.mark.anyio()
    async def test_found(
        self,
        service: NotesService,
        repo: AsyncMock,
        user_id: uuid.UUID,
    ) -> None:
        note = _mock_note(user_id=user_id)
        repo.get_note_by_id.return_value = note

        result = await service.get(user_id, note.id)

        assert result.id == note.id

    @pytest.mark.anyio()
    async def test_not_found(
        self,
        service: NotesService,
        repo: AsyncMock,
        user_id: uuid.UUID,
    ) -> None:
        repo.get_note_by_id.return_value = None

        with pytest.raises(NotFoundError):
            await service.get(user_id, uuid.uuid4())


# --- list ---


class TestList:
    @pytest.mark.anyio()
    async def test_returns_notes(
        self,
        service: NotesService,
        repo: AsyncMock,
        user_id: uuid.UUID,
    ) -> None:
        notes = [_mock_note(user_id=user_id), _mock_note(user_id=user_id)]
        repo.list_notes.return_value = (notes, 2)

        result = await service.list(user_id)

        assert result.total == 2
        assert len(result.items) == 2

    @pytest.mark.anyio()
    async def test_empty(
        self,
        service: NotesService,
        repo: AsyncMock,
        user_id: uuid.UUID,
    ) -> None:
        repo.list_notes.return_value = ([], 0)

        result = await service.list(user_id)

        assert result.items == []
        assert result.total == 0

    @pytest.mark.anyio()
    async def test_passes_filters(
        self,
        service: NotesService,
        repo: AsyncMock,
        user_id: uuid.UUID,
    ) -> None:
        tag_id = uuid.uuid4()
        repo.list_notes.return_value = ([], 0)

        await service.list(
            user_id, limit=10, offset=5, deleted=True, search="test", tag_ids=[tag_id]
        )

        repo.list_notes.assert_called_once_with(user_id, 10, 5, True, "test", [tag_id])


# --- update ---


class TestUpdate:
    @pytest.mark.anyio()
    async def test_update_title(
        self,
        service: NotesService,
        repo: AsyncMock,
        rag: AsyncMock,
        user_id: uuid.UUID,
    ) -> None:
        note = _mock_note(user_id=user_id, version=1)
        updated = _mock_note(user_id=user_id, title="New Title", version=2)
        repo.get_active_note.return_value = note
        repo.update_note.return_value = updated

        result = await service.update(user_id, note.id, version=1, title="New Title")

        assert result.title == "New Title"
        rag.index_note.assert_called_once()

    @pytest.mark.anyio()
    async def test_update_content_only(
        self,
        service: NotesService,
        repo: AsyncMock,
        user_id: uuid.UUID,
    ) -> None:
        note = _mock_note(user_id=user_id, title="Keep This", version=1)
        repo.get_active_note.return_value = note
        repo.update_note.return_value = note

        await service.update(user_id, note.id, version=1, content="New content")

        # title should be note.title (unchanged)
        call_args = repo.update_note.call_args
        assert call_args[0][1] == "Keep This"  # title preserved

    @pytest.mark.anyio()
    async def test_unset_fields_preserved(
        self,
        service: NotesService,
        repo: AsyncMock,
        user_id: uuid.UUID,
    ) -> None:
        note = _mock_note(user_id=user_id, title="Original", content="Original content", version=1)
        repo.get_active_note.return_value = note
        repo.update_note.return_value = note

        await service.update(user_id, note.id, version=1)  # no title or content

        call_args = repo.update_note.call_args
        assert call_args[0][1] == "Original"
        assert call_args[0][2] == "Original content"

    @pytest.mark.anyio()
    async def test_set_title_to_none(
        self,
        service: NotesService,
        repo: AsyncMock,
        user_id: uuid.UUID,
    ) -> None:
        note = _mock_note(user_id=user_id, version=1)
        repo.get_active_note.return_value = note
        repo.update_note.return_value = note

        await service.update(user_id, note.id, version=1, title=None)

        call_args = repo.update_note.call_args
        assert call_args[0][1] is None  # title explicitly set to None

    @pytest.mark.anyio()
    async def test_version_conflict(
        self,
        service: NotesService,
        repo: AsyncMock,
        user_id: uuid.UUID,
    ) -> None:
        note = _mock_note(user_id=user_id, version=2)
        repo.get_active_note.return_value = note

        with pytest.raises(ConflictError, match="Version conflict"):
            await service.update(user_id, note.id, version=1, title="New")

    @pytest.mark.anyio()
    async def test_not_found(
        self,
        service: NotesService,
        repo: AsyncMock,
        user_id: uuid.UUID,
    ) -> None:
        repo.get_active_note.return_value = None

        with pytest.raises(NotFoundError):
            await service.update(user_id, uuid.uuid4(), version=1, title="New")


# --- soft_delete ---


class TestSoftDelete:
    @pytest.mark.anyio()
    async def test_success(
        self,
        service: NotesService,
        repo: AsyncMock,
        rag: AsyncMock,
        user_id: uuid.UUID,
    ) -> None:
        note = _mock_note(user_id=user_id)
        repo.get_active_note.return_value = note

        await service.soft_delete(user_id, note.id)

        repo.soft_delete_note.assert_called_once()
        rag.remove_note.assert_called_once_with(note.id)

    @pytest.mark.anyio()
    async def test_not_found(
        self,
        service: NotesService,
        repo: AsyncMock,
        user_id: uuid.UUID,
    ) -> None:
        repo.get_active_note.return_value = None

        with pytest.raises(NotFoundError):
            await service.soft_delete(user_id, uuid.uuid4())


# --- restore ---


class TestRestore:
    @pytest.mark.anyio()
    async def test_success(
        self,
        service: NotesService,
        repo: AsyncMock,
        rag: AsyncMock,
        user_id: uuid.UUID,
    ) -> None:
        note = _mock_note(user_id=user_id, deleted_at=datetime.now(UTC))
        restored = _mock_note(user_id=user_id, deleted_at=None)
        repo.get_deleted_note.return_value = note
        repo.restore_note.return_value = restored

        result = await service.restore(user_id, note.id)

        assert result.deleted_at is None
        rag.index_note.assert_called_once()

    @pytest.mark.anyio()
    async def test_not_found(
        self,
        service: NotesService,
        repo: AsyncMock,
        user_id: uuid.UUID,
    ) -> None:
        repo.get_deleted_note.return_value = None

        with pytest.raises(NotFoundError):
            await service.restore(user_id, uuid.uuid4())


# --- hard_delete ---


class TestHardDelete:
    @pytest.mark.anyio()
    async def test_success(
        self,
        service: NotesService,
        repo: AsyncMock,
        rag: AsyncMock,
        user_id: uuid.UUID,
    ) -> None:
        note = _mock_note(user_id=user_id, deleted_at=datetime.now(UTC))
        repo.get_deleted_note.return_value = note

        await service.hard_delete(user_id, note.id)

        rag.remove_note.assert_called_once_with(note.id)
        repo.hard_delete_note.assert_called_once_with(note)

    @pytest.mark.anyio()
    async def test_not_found(
        self,
        service: NotesService,
        repo: AsyncMock,
        user_id: uuid.UUID,
    ) -> None:
        repo.get_deleted_note.return_value = None

        with pytest.raises(NotFoundError):
            await service.hard_delete(user_id, uuid.uuid4())


# --- update_tags ---


class TestUpdateTags:
    @pytest.mark.anyio()
    async def test_success(
        self,
        service: NotesService,
        repo: AsyncMock,
        tags_repo: AsyncMock,
        user_id: uuid.UUID,
    ) -> None:
        note = _mock_note(user_id=user_id)
        tag_id = uuid.uuid4()
        tags_repo.verify_tags_belong_to_user.return_value = [tag_id]

        updated = _mock_note(user_id=user_id, tags=[_mock_tag(tag_id, "work")])
        repo.get_active_note.side_effect = [note, updated]

        result = await service.update_tags(user_id, note.id, [tag_id])

        repo.set_note_tags.assert_called_once_with(note.id, [tag_id])
        assert len(result.tags) == 1

    @pytest.mark.anyio()
    async def test_clear_tags(
        self,
        service: NotesService,
        repo: AsyncMock,
        user_id: uuid.UUID,
    ) -> None:
        note = _mock_note(user_id=user_id)
        repo.get_active_note.side_effect = [note, _mock_note(user_id=user_id, tags=[])]

        result = await service.update_tags(user_id, note.id, [])

        repo.set_note_tags.assert_called_once_with(note.id, [])
        assert result.tags == []

    @pytest.mark.anyio()
    async def test_too_many_tags(
        self,
        service: NotesService,
        repo: AsyncMock,
        user_id: uuid.UUID,
    ) -> None:
        note = _mock_note(user_id=user_id)
        repo.get_active_note.return_value = note

        with pytest.raises(ValidationError, match="tags"):
            await service.update_tags(user_id, note.id, [uuid.uuid4() for _ in range(11)])

    @pytest.mark.anyio()
    async def test_tags_not_found(
        self,
        service: NotesService,
        repo: AsyncMock,
        tags_repo: AsyncMock,
        user_id: uuid.UUID,
    ) -> None:
        note = _mock_note(user_id=user_id)
        repo.get_active_note.return_value = note
        tag_ids = [uuid.uuid4(), uuid.uuid4()]
        tags_repo.verify_tags_belong_to_user.return_value = [tag_ids[0]]

        with pytest.raises(NotFoundError, match="tags not found"):
            await service.update_tags(user_id, note.id, tag_ids)

    @pytest.mark.anyio()
    async def test_note_not_found(
        self,
        service: NotesService,
        repo: AsyncMock,
        user_id: uuid.UUID,
    ) -> None:
        repo.get_active_note.return_value = None

        with pytest.raises(NotFoundError):
            await service.update_tags(user_id, uuid.uuid4(), [])


# --- batch_get ---


class TestBatchGet:
    @pytest.mark.anyio()
    async def test_returns_notes(
        self,
        service: NotesService,
        repo: AsyncMock,
        user_id: uuid.UUID,
    ) -> None:
        notes = [_mock_note(user_id=user_id), _mock_note(user_id=user_id)]
        repo.get_notes_by_ids.return_value = notes

        result = await service.batch_get(user_id, [n.id for n in notes])

        assert len(result.items) == 2

    @pytest.mark.anyio()
    async def test_empty(
        self,
        service: NotesService,
        repo: AsyncMock,
        user_id: uuid.UUID,
    ) -> None:
        repo.get_notes_by_ids.return_value = []

        result = await service.batch_get(user_id, [])

        assert result.items == []


# --- search_keywords ---


class TestSearchKeywords:
    @pytest.mark.anyio()
    async def test_returns_matching_notes(
        self,
        service: NotesService,
        repo: AsyncMock,
        user_id: uuid.UUID,
    ) -> None:
        notes = [_mock_note(user_id=user_id, title="Python Guide")]
        repo.search_by_keywords.return_value = (notes, 1)

        result = await service.search_keywords(user_id, ["python"], limit=50)

        assert result.total == 1
        assert len(result.items) == 1
        assert result.keywords == ["python"]

    @pytest.mark.anyio()
    async def test_empty_result(
        self,
        service: NotesService,
        repo: AsyncMock,
        user_id: uuid.UUID,
    ) -> None:
        repo.search_by_keywords.return_value = ([], 0)

        result = await service.search_keywords(user_id, ["nonexistent"], limit=50)

        assert result.total == 0
        assert result.items == []

    @pytest.mark.anyio()
    async def test_passes_keywords_and_limit_to_repo(
        self,
        service: NotesService,
        repo: AsyncMock,
        user_id: uuid.UUID,
    ) -> None:
        repo.search_by_keywords.return_value = ([], 0)

        await service.search_keywords(user_id, ["python", "async"], limit=20)

        repo.search_by_keywords.assert_called_once_with(user_id, ["python", "async"], 20)

    @pytest.mark.anyio()
    async def test_strips_whitespace_from_keywords(
        self,
        service: NotesService,
        repo: AsyncMock,
        user_id: uuid.UUID,
    ) -> None:
        repo.search_by_keywords.return_value = ([], 0)

        await service.search_keywords(user_id, ["  python  ", " async "], limit=50)

        repo.search_by_keywords.assert_called_once_with(user_id, ["python", "async"], 50)

    @pytest.mark.anyio()
    async def test_filters_empty_keywords(
        self,
        service: NotesService,
        repo: AsyncMock,
        user_id: uuid.UUID,
    ) -> None:
        repo.search_by_keywords.return_value = ([], 0)

        await service.search_keywords(user_id, ["", "  ", "python"], limit=50)

        repo.search_by_keywords.assert_called_once_with(user_id, ["python"], 50)

    @pytest.mark.anyio()
    async def test_response_echoes_limit(
        self,
        service: NotesService,
        repo: AsyncMock,
        user_id: uuid.UUID,
    ) -> None:
        repo.search_by_keywords.return_value = ([], 0)

        result = await service.search_keywords(user_id, ["test"], limit=25)

        assert result.limit == 25
