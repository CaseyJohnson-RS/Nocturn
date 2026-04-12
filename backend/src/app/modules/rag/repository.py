import uuid

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.app.modules.rag.models import EmbeddingTask, NoteChunk


class RAGRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    # --- Chunks ---

    async def delete_chunks_for_note(self, note_id: uuid.UUID) -> None:
        await self.db.execute(delete(NoteChunk).where(NoteChunk.note_id == note_id))

    async def create_chunks(self, chunks: list[NoteChunk]) -> None:
        self.db.add_all(chunks)
        await self.db.flush()

    async def set_chunk_embeddings(
        self, chunk_ids: list[uuid.UUID], embeddings: list[list[float]]
    ) -> None:
        for cid, emb in zip(chunk_ids, embeddings):
            await self.db.execute(
                update(NoteChunk).where(NoteChunk.id == cid).values(embedding=emb)
            )

    async def search_similar(
        self,
        user_id: uuid.UUID,
        query_embedding: list[float],
        limit: int = 10,
    ) -> list[tuple[NoteChunk, float]]:
        """Find the most similar chunks for a user using cosine distance.

        Returns list of (chunk, score) tuples where score is 1 - cosine_distance.
        """
        distance = NoteChunk.embedding.cosine_distance(query_embedding).label("distance")
        result = await self.db.execute(
            select(NoteChunk, distance)
            .where(
                NoteChunk.user_id == user_id,
                NoteChunk.embedding.is_not(None),
            )
            .order_by(distance)
            .limit(limit)
        )
        return [(row[0], 1.0 - row[1]) for row in result.all()]

    async def get_chunks_for_note(self, note_id: uuid.UUID) -> list[NoteChunk]:
        result = await self.db.execute(
            select(NoteChunk).where(NoteChunk.note_id == note_id).order_by(NoteChunk.chunk_index)
        )
        return list(result.scalars().all())

    # --- Embedding queue ---

    async def enqueue(self, note_id: uuid.UUID, user_id: uuid.UUID) -> None:
        existing = await self.db.execute(
            select(EmbeddingTask).where(EmbeddingTask.note_id == note_id)
        )
        task = existing.scalar_one_or_none()
        if task:
            task.status = "pending"
            task.attempts = 0
            task.error = None
        else:
            self.db.add(EmbeddingTask(note_id=note_id, user_id=user_id))
        await self.db.flush()

    async def get_pending_tasks(self, limit: int = 20) -> list[EmbeddingTask]:
        result = await self.db.execute(
            select(EmbeddingTask)
            .where(EmbeddingTask.status == "pending")
            .order_by(EmbeddingTask.created_at)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def mark_processing(self, task_id: uuid.UUID) -> None:
        await self.db.execute(
            update(EmbeddingTask).where(EmbeddingTask.id == task_id).values(status="processing")
        )

    async def mark_done(self, task_id: uuid.UUID) -> None:
        await self.db.execute(delete(EmbeddingTask).where(EmbeddingTask.id == task_id))

    async def mark_failed(self, task_id: uuid.UUID, error: str, attempts: int) -> None:
        from src.app.config import settings

        new_status = "failed" if attempts >= settings.embedding_max_attempts else "pending"
        await self.db.execute(
            update(EmbeddingTask)
            .where(EmbeddingTask.id == task_id)
            .values(status=new_status, error=error, attempts=attempts)
        )

    async def remove_task(self, note_id: uuid.UUID) -> None:
        await self.db.execute(delete(EmbeddingTask).where(EmbeddingTask.note_id == note_id))
