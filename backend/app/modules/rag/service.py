import logging
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.common.exceptions import NotFoundError
from app.common.routerai import create_embeddings
from app.config import settings
from app.modules.notes.models import Note
from app.modules.notes.repository import NotesRepository
from app.modules.rag.models import NoteChunk
from app.modules.rag.repository import RAGRepository
from app.modules.rag.schemas import SearchResponse, SearchResult

logger = logging.getLogger(__name__)


def chunk_text(text: str, title: str | None = None) -> list[str]:
    """Split text into overlapping chunks based on configured token/char settings."""
    if not text:
        return []

    chars_per_token = settings.planner_chars_per_token
    chunk_chars = int(settings.chunk_size_tokens * chars_per_token)
    overlap_chars = int(settings.chunk_overlap_tokens * chars_per_token)
    step = max(chunk_chars - overlap_chars, 1)

    prefix = f"[{title}] " if title else ""

    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = start + chunk_chars
        chunks.append(prefix + text[start:end])
        start += step

    return chunks


def get_chunk_by_index(text: str | None, index: int, title: str | None = None) -> str:
    """Reconstruct a specific chunk by its index."""
    if not text:
        return ''

    chars_per_token = settings.planner_chars_per_token
    chunk_chars = int(settings.chunk_size_tokens * chars_per_token)
    overlap_chars = int(settings.chunk_overlap_tokens * chars_per_token)
    step = max(chunk_chars - overlap_chars, 1)

    start = index * step
    if start >= len(text):
        return ''

    prefix = f"[{title}] " if title else ''
    return prefix + text[start : start + chunk_chars]


class RAGService:
    def __init__(self, db: AsyncSession):
        self.rag_repo = RAGRepository(db)
        self.note_repo = NotesRepository(db)

    async def index_note(self, note: Note) -> None:
        full_text = f"{note.title}\n\n{note.content}"

        if not full_text.strip():
            await self.rag_repo.delete_chunks_for_note(note.id)
            await self.rag_repo.remove_task(note.id)
            return

        await self.rag_repo.enqueue(note.id, note.user_id)

    async def remove_note(self, note_id: uuid.UUID) -> None:
        """Remove all chunks and queue entry for a note."""
        await self.rag_repo.delete_chunks_for_note(note_id)
        await self.rag_repo.remove_task(note_id)

    async def embed_note(self, note_id: uuid.UUID, user_id: uuid.UUID) -> None:
        """Chunk, generate and store embeddings for all chunks of a note."""

        note = await self.note_repo.get_note_by_id(note_id=note_id, user_id=user_id)

        if not note:
            raise NotFoundError("Note not found")

        await self.rag_repo.delete_chunks_for_note(note_id)

        texts = chunk_text(note.content or "", note.title or "")
        chunk_objs: list[NoteChunk] = [
            NoteChunk(
                note_id=note.id,
                user_id=note.user_id,
                chunk_index=i,
            )
            for i in range(len(texts))
        ]
        await self.rag_repo.create_chunks(chunk_objs)

        chunks: list[NoteChunk] = await self.rag_repo.get_chunks_for_note(note_id)
        if not chunks:
            return

        embeddings = await create_embeddings(texts)
        chunk_ids = [c.id for c in chunks]
        await self.rag_repo.set_chunk_embeddings(chunk_ids, embeddings)

    async def search(self, user_id: uuid.UUID, query: str, limit: int = 5) -> SearchResponse:
        query_embedding = (await create_embeddings([query]))[0]
        rows = await self.rag_repo.search_similar(user_id, query_embedding, limit)

        note_ids = list({chunk.note_id for chunk, _ in rows})
        notes = await self.note_repo.get_notes_by_ids(note_ids, user_id)
        note_map = {n.id: n for n in notes}

        results: list[SearchResult] = []
        for chunk, score in rows:
            note = note_map.get(chunk.note_id)
            if not note:
                continue
            results.append(
                SearchResult(
                    chunk_id=chunk.id,
                    note_id=chunk.note_id,
                    chunk_index=chunk.chunk_index,
                    content=get_chunk_by_index(note.content, chunk.chunk_index, note.title),
                    score=round(score, 4),
                )
            )

        return SearchResponse(results=results)
