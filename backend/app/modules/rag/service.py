import logging
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.common.routerai import create_embeddings
from app.config import settings
from app.modules.notes.models import Note
from app.modules.rag.models import NoteChunk
from app.modules.rag.repository import RAGRepository
from app.modules.rag.schemas import SearchResult, SearchResponse

logger = logging.getLogger(__name__)


def chunk_text(text: str) -> list[str]:
    """Split text into overlapping chunks based on configured token/char settings."""
    if not text:
        return []

    chars_per_token = settings.planner_chars_per_token
    chunk_chars = int(settings.chunk_size_tokens * chars_per_token)
    overlap_chars = int(settings.chunk_overlap_tokens * chars_per_token)
    step = max(chunk_chars - overlap_chars, 1)

    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_chars
        chunks.append(text[start:end])
        start += step

    return chunks


class RAGService:
    def __init__(self, db: AsyncSession):
        self.repo = RAGRepository(db)

    async def index_note(self, note: Note) -> None:
        """Chunk a note, store chunks, and queue for embedding."""
        # Build text from title + content
        parts = []
        if note.title:
            parts.append(note.title)
        if note.content:
            parts.append(note.content)
        full_text = "\n\n".join(parts)

        # Remove old chunks
        await self.repo.delete_chunks_for_note(note.id)

        if not full_text.strip():
            await self.repo.remove_task(note.id)
            return

        # Create new chunks
        texts = chunk_text(full_text)
        chunk_objs = [
            NoteChunk(
                note_id=note.id,
                user_id=note.user_id,
                chunk_index=i,
                content=t,
            )
            for i, t in enumerate(texts)
        ]
        await self.repo.create_chunks(chunk_objs)

        # Queue for embedding
        await self.repo.enqueue(note.id)

    async def remove_note(self, note_id: uuid.UUID) -> None:
        """Remove all chunks and queue entry for a note."""
        await self.repo.delete_chunks_for_note(note_id)
        await self.repo.remove_task(note_id)

    async def embed_note_chunks(self, note_id: uuid.UUID) -> None:
        """Generate and store embeddings for all chunks of a note."""
        chunks = await self.repo.get_chunks_for_note(note_id)
        if not chunks:
            return

        texts = [c.content for c in chunks]
        embeddings = await create_embeddings(texts)
        chunk_ids = [c.id for c in chunks]
        await self.repo.set_chunk_embeddings(chunk_ids, embeddings)

    async def search(
        self,
        user_id: uuid.UUID,
        query: str,
        limit: int = 5,
    ) -> SearchResponse:
        """Semantic search over a user's note chunks."""
        query_embedding = (await create_embeddings([query]))[0]

        rows = await self.repo.search_similar(user_id, query_embedding, limit)

        results = [
            SearchResult(
                chunk_id=chunk.id,
                note_id=chunk.note_id,
                chunk_index=chunk.chunk_index,
                content=chunk.content,
                score=round(score, 4),
            )
            for chunk, score in rows
        ]
        return SearchResponse(results=results)
