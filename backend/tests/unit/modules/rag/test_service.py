"""Unit tests for RAGService."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.app.common.exceptions import NotFoundError
from src.app.modules.rag.service import RAGService, chunk_text, get_chunk_by_index

# --- chunk_text ---


class TestChunkText:
    def test_empty_text(self) -> None:
        assert chunk_text("") == []

    def test_short_text(self) -> None:
        chunks = chunk_text("hello")
        assert len(chunks) == 1
        assert chunks[0] == "hello"

    def test_with_title(self) -> None:
        chunks = chunk_text("hello", title="My Note")
        assert chunks[0] == "[My Note] hello"

    def test_without_title(self) -> None:
        chunks = chunk_text("hello", title=None)
        assert chunks[0] == "hello"

    @patch("src.app.modules.rag.service.settings")
    def test_produces_overlapping_chunks(self, mock_settings: MagicMock) -> None:
        mock_settings.planner_chars_per_token = 1.0
        mock_settings.chunk_size_tokens = 10
        mock_settings.chunk_overlap_tokens = 3

        text = "a" * 25
        chunks = chunk_text(text)

        assert len(chunks) > 1
        # step = 10 - 3 = 7, so chunks start at 0, 7, 14, 21
        assert len(chunks) == 4


# --- get_chunk_by_index ---


class TestGetChunkByIndex:
    def test_empty_text(self) -> None:
        assert get_chunk_by_index("", 0) == ""
        assert get_chunk_by_index(None, 0) == ""

    @patch("src.app.modules.rag.service.settings")
    def test_valid_index(self, mock_settings: MagicMock) -> None:
        mock_settings.planner_chars_per_token = 1.0
        mock_settings.chunk_size_tokens = 10
        mock_settings.chunk_overlap_tokens = 3

        text = "a" * 25
        result = get_chunk_by_index(text, 1)

        # step = 7, so index 1 starts at 7
        assert result == text[7:17]

    @patch("src.app.modules.rag.service.settings")
    def test_with_title(self, mock_settings: MagicMock) -> None:
        mock_settings.planner_chars_per_token = 1.0
        mock_settings.chunk_size_tokens = 10
        mock_settings.chunk_overlap_tokens = 3

        result = get_chunk_by_index("hello world", 0, title="Note")
        assert result.startswith("[Note] ")

    @patch("src.app.modules.rag.service.settings")
    def test_out_of_range(self, mock_settings: MagicMock) -> None:
        mock_settings.planner_chars_per_token = 1.0
        mock_settings.chunk_size_tokens = 10
        mock_settings.chunk_overlap_tokens = 3

        assert get_chunk_by_index("short", 100) == ""

    @patch("src.app.modules.rag.service.settings")
    def test_matches_chunk_text(self, mock_settings: MagicMock) -> None:
        mock_settings.planner_chars_per_token = 1.0
        mock_settings.chunk_size_tokens = 10
        mock_settings.chunk_overlap_tokens = 3

        text = "abcdefghijklmnopqrstuvwxyz"
        chunks = chunk_text(text, title="T")

        for i, chunk in enumerate(chunks):
            assert get_chunk_by_index(text, i, title="T") == chunk


# --- Fixtures ---


@pytest.fixture()
def rag_repo() -> AsyncMock:
    return AsyncMock()


@pytest.fixture()
def note_repo() -> AsyncMock:
    return AsyncMock()


@pytest.fixture()
def service(rag_repo: AsyncMock, note_repo: AsyncMock) -> RAGService:
    svc = RAGService.__new__(RAGService)
    svc.rag_repo = rag_repo
    svc.note_repo = note_repo
    return svc


def _mock_note(
    note_id: uuid.UUID | None = None,
    user_id: uuid.UUID | None = None,
    title: str = "Test Note",
    content: str = "Some content",
) -> MagicMock:
    n = MagicMock()
    n.id = note_id or uuid.uuid4()
    n.user_id = user_id or uuid.uuid4()
    n.title = title
    n.content = content
    return n


def _mock_chunk(
    note_id: uuid.UUID,
    chunk_index: int = 0,
    user_id: uuid.UUID | None = None,
) -> MagicMock:
    c = MagicMock()
    c.id = uuid.uuid4()
    c.note_id = note_id
    c.user_id = user_id or uuid.uuid4()
    c.chunk_index = chunk_index
    return c


# --- index_note ---


class TestIndexNote:
    @pytest.mark.anyio()
    async def test_enqueues_non_empty_note(
        self,
        service: RAGService,
        rag_repo: AsyncMock,
    ) -> None:
        note = _mock_note(title="Title", content="Content")

        await service.index_note(note)

        rag_repo.enqueue.assert_called_once_with(note.id, note.user_id)

    @pytest.mark.anyio()
    async def test_empty_note_removes_chunks(
        self,
        service: RAGService,
        rag_repo: AsyncMock,
    ) -> None:
        note = _mock_note(title="", content="")

        await service.index_note(note)

        rag_repo.delete_chunks_for_note.assert_called_once_with(note.id)
        rag_repo.remove_task.assert_called_once_with(note.id)
        rag_repo.enqueue.assert_not_called()

    @pytest.mark.anyio()
    async def test_whitespace_only_note_removes_chunks(
        self,
        service: RAGService,
        rag_repo: AsyncMock,
    ) -> None:
        note = _mock_note(title="   ", content="   ")

        await service.index_note(note)

        rag_repo.delete_chunks_for_note.assert_called_once()
        rag_repo.enqueue.assert_not_called()


# --- remove_note ---


class TestRemoveNote:
    @pytest.mark.anyio()
    async def test_removes_chunks_and_task(
        self,
        service: RAGService,
        rag_repo: AsyncMock,
    ) -> None:
        note_id = uuid.uuid4()

        await service.remove_note(note_id)

        rag_repo.delete_chunks_for_note.assert_called_once_with(note_id)
        rag_repo.remove_task.assert_called_once_with(note_id)


# --- embed_note ---


class TestEmbedNote:
    @pytest.mark.anyio()
    async def test_success(
        self,
        service: RAGService,
        rag_repo: AsyncMock,
        note_repo: AsyncMock,
    ) -> None:
        note = _mock_note(content="Some text for embedding")
        note_repo.get_note_by_id.return_value = note

        chunk = _mock_chunk(note.id)
        rag_repo.get_chunks_for_note.return_value = [chunk]

        with patch(
            "src.app.modules.rag.service.create_embeddings",
            new_callable=AsyncMock,
        ) as mock_embed:
            mock_embed.return_value = [[0.1, 0.2, 0.3]]

            await service.embed_note(note.id, note.user_id)

        rag_repo.delete_chunks_for_note.assert_called_once_with(note.id)
        rag_repo.create_chunks.assert_called_once()
        rag_repo.set_chunk_embeddings.assert_called_once()

    @pytest.mark.anyio()
    async def test_note_not_found(
        self,
        service: RAGService,
        note_repo: AsyncMock,
    ) -> None:
        note_repo.get_note_by_id.return_value = None

        with pytest.raises(NotFoundError):
            await service.embed_note(uuid.uuid4(), uuid.uuid4())

    @pytest.mark.anyio()
    async def test_empty_content_creates_no_chunks(
        self,
        service: RAGService,
        rag_repo: AsyncMock,
        note_repo: AsyncMock,
    ) -> None:
        note = _mock_note(content="")
        note_repo.get_note_by_id.return_value = note
        rag_repo.get_chunks_for_note.return_value = []

        with patch("src.app.modules.rag.service.create_embeddings", new_callable=AsyncMock):
            await service.embed_note(note.id, note.user_id)

        rag_repo.set_chunk_embeddings.assert_not_called()


# --- search ---


class TestSearch:
    @pytest.mark.anyio()
    async def test_returns_results(
        self,
        service: RAGService,
        rag_repo: AsyncMock,
        note_repo: AsyncMock,
    ) -> None:
        note = _mock_note()
        chunk = _mock_chunk(note.id, chunk_index=0)

        rag_repo.search_similar.return_value = [(chunk, 0.95)]
        note_repo.get_notes_by_ids.return_value = [note]

        with patch(
            "src.app.modules.rag.service.create_embeddings",
            new_callable=AsyncMock,
        ) as mock_embed:
            mock_embed.return_value = [[0.1, 0.2]]

            result = await service.search(note.user_id, "query")

        assert len(result.results) == 1
        assert result.results[0].note_id == note.id
        assert result.results[0].score == 0.95

    @pytest.mark.anyio()
    async def test_skips_deleted_notes(
        self,
        service: RAGService,
        rag_repo: AsyncMock,
        note_repo: AsyncMock,
    ) -> None:
        chunk = _mock_chunk(uuid.uuid4())
        rag_repo.search_similar.return_value = [(chunk, 0.9)]
        note_repo.get_notes_by_ids.return_value = []  # note deleted

        with patch(
            "src.app.modules.rag.service.create_embeddings",
            new_callable=AsyncMock,
        ) as mock_embed:
            mock_embed.return_value = [[0.1]]

            result = await service.search(uuid.uuid4(), "query")

        assert len(result.results) == 0

    @pytest.mark.anyio()
    async def test_no_results(
        self,
        service: RAGService,
        rag_repo: AsyncMock,
    ) -> None:
        rag_repo.search_similar.return_value = []

        with patch(
            "src.app.modules.rag.service.create_embeddings",
            new_callable=AsyncMock,
        ) as mock_embed:
            mock_embed.return_value = [[0.1]]

            result = await service.search(uuid.uuid4(), "query")

        assert result.results == []
