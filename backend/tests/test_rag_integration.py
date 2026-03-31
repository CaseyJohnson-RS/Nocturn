"""Integration tests for the RAG module."""

import uuid
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.auth.models import User
from app.modules.rag.models import EmbeddingTask, NoteChunk


# --- Helpers ---

async def register_and_login(client: AsyncClient, db: AsyncSession, email="rag@test.com") -> str:
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


FAKE_DIM = 2560
FAKE_EMBEDDING = [0.1] * FAKE_DIM


def make_fake_embeddings(texts: list[str]) -> list[list[float]]:
    """Return deterministic fake embeddings, one per input text."""
    return [FAKE_EMBEDDING for _ in texts]


# --- Chunking & Indexing ---

class TestRAGIndexing:
    @patch("app.modules.rag.service.create_embeddings", new_callable=AsyncMock)
    async def test_create_note_queues_embedding(
        self, mock_embed, client: AsyncClient, db: AsyncSession,
    ):
        mock_embed.side_effect = make_fake_embeddings
        token = await register_and_login(client, db)

        resp = await client.post("/api/notes", json={
            "title": "RAG Test",
            "content": "This is a test note for RAG indexing.",
        }, headers=auth(token))
        assert resp.status_code == 201
        note_id = resp.json()["id"]

        # Check chunks were created
        result = await db.execute(
            select(NoteChunk).where(NoteChunk.note_id == uuid.UUID(note_id))
        )
        chunks = result.scalars().all()
        assert len(chunks) >= 1
        assert chunks[0].content is not None

        # Check embedding task was queued
        result = await db.execute(
            select(EmbeddingTask).where(EmbeddingTask.note_id == uuid.UUID(note_id))
        )
        task = result.scalar_one_or_none()
        assert task is not None
        assert task.status == "pending"

    @patch("app.modules.rag.service.create_embeddings", new_callable=AsyncMock)
    async def test_update_note_reindexes(
        self, mock_embed, client: AsyncClient, db: AsyncSession,
    ):
        mock_embed.side_effect = make_fake_embeddings
        token = await register_and_login(client, db)

        resp = await client.post("/api/notes", json={
            "title": "Original",
            "content": "Original content",
        }, headers=auth(token))
        note_id = resp.json()["id"]

        # Update the note
        await client.put(f"/api/notes/{note_id}", json={
            "title": "Updated",
            "content": "Updated content with more detail for RAG.",
            "version": 1,
        }, headers=auth(token))

        # Chunks should reflect updated content
        result = await db.execute(
            select(NoteChunk).where(NoteChunk.note_id == uuid.UUID(note_id))
        )
        chunks = result.scalars().all()
        assert len(chunks) >= 1
        assert "Updated" in chunks[0].content

    @patch("app.modules.rag.service.create_embeddings", new_callable=AsyncMock)
    async def test_empty_note_no_chunks(
        self, mock_embed, client: AsyncClient, db: AsyncSession,
    ):
        mock_embed.side_effect = make_fake_embeddings
        token = await register_and_login(client, db)

        resp = await client.post("/api/notes", json={}, headers=auth(token))
        assert resp.status_code == 201
        note_id = resp.json()["id"]

        result = await db.execute(
            select(NoteChunk).where(NoteChunk.note_id == uuid.UUID(note_id))
        )
        chunks = result.scalars().all()
        assert len(chunks) == 0


# --- Soft-delete / Restore ---

class TestRAGDeleteRestore:
    @patch("app.modules.rag.service.create_embeddings", new_callable=AsyncMock)
    async def test_soft_delete_removes_chunks(
        self, mock_embed, client: AsyncClient, db: AsyncSession,
    ):
        mock_embed.side_effect = make_fake_embeddings
        token = await register_and_login(client, db)

        resp = await client.post("/api/notes", json={
            "title": "To Delete",
            "content": "Content to be removed from search index.",
        }, headers=auth(token))
        note_id = resp.json()["id"]

        # Verify chunks exist
        result = await db.execute(
            select(NoteChunk).where(NoteChunk.note_id == uuid.UUID(note_id))
        )
        assert len(result.scalars().all()) >= 1

        # Soft-delete
        resp = await client.delete(f"/api/notes/{note_id}", headers=auth(token))
        assert resp.status_code == 204

        # Chunks should be removed
        result = await db.execute(
            select(NoteChunk).where(NoteChunk.note_id == uuid.UUID(note_id))
        )
        assert len(result.scalars().all()) == 0

        # Embedding task should be removed
        result = await db.execute(
            select(EmbeddingTask).where(EmbeddingTask.note_id == uuid.UUID(note_id))
        )
        assert result.scalar_one_or_none() is None

    @patch("app.modules.rag.service.create_embeddings", new_callable=AsyncMock)
    async def test_restore_reindexes_note(
        self, mock_embed, client: AsyncClient, db: AsyncSession,
    ):
        mock_embed.side_effect = make_fake_embeddings
        token = await register_and_login(client, db)

        resp = await client.post("/api/notes", json={
            "title": "To Restore",
            "content": "This will be deleted then restored.",
        }, headers=auth(token))
        note_id = resp.json()["id"]

        # Soft-delete
        await client.delete(f"/api/notes/{note_id}", headers=auth(token))

        # Restore
        resp = await client.post(f"/api/notes/{note_id}/restore", headers=auth(token))
        assert resp.status_code == 200

        # Chunks should be re-created
        result = await db.execute(
            select(NoteChunk).where(NoteChunk.note_id == uuid.UUID(note_id))
        )
        assert len(result.scalars().all()) >= 1

        # Embedding task should be re-queued
        result = await db.execute(
            select(EmbeddingTask).where(EmbeddingTask.note_id == uuid.UUID(note_id))
        )
        task = result.scalar_one_or_none()
        assert task is not None
        assert task.status == "pending"

    @patch("app.modules.rag.service.create_embeddings", new_callable=AsyncMock)
    async def test_hard_delete_removes_chunks(
        self, mock_embed, client: AsyncClient, db: AsyncSession,
    ):
        mock_embed.side_effect = make_fake_embeddings
        token = await register_and_login(client, db)

        resp = await client.post("/api/notes", json={
            "title": "To Hard Delete",
            "content": "Permanent removal.",
        }, headers=auth(token))
        note_id = resp.json()["id"]

        await client.delete(f"/api/notes/{note_id}", headers=auth(token))
        resp = await client.delete(
            f"/api/notes/{note_id}", params={"permanent": "true"}, headers=auth(token),
        )
        assert resp.status_code == 204

        # Both chunks and tasks should be gone
        result = await db.execute(
            select(NoteChunk).where(NoteChunk.note_id == uuid.UUID(note_id))
        )
        assert len(result.scalars().all()) == 0


# --- Search ---

class TestRAGSearch:
    @patch("app.modules.rag.service.create_embeddings", new_callable=AsyncMock)
    async def test_search_requires_auth(self, mock_embed, client: AsyncClient):
        resp = await client.post("/api/rag/search", json={"query": "test"})
        assert resp.status_code == 401

    @patch("app.modules.rag.service.create_embeddings", new_callable=AsyncMock)
    async def test_search_empty_results(
        self, mock_embed, client: AsyncClient, db: AsyncSession,
    ):
        mock_embed.side_effect = make_fake_embeddings
        token = await register_and_login(client, db)

        resp = await client.post(
            "/api/rag/search",
            json={"query": "anything"},
            headers=auth(token),
        )
        assert resp.status_code == 200
        assert resp.json()["results"] == []

    @patch("app.modules.rag.service.create_embeddings", new_callable=AsyncMock)
    async def test_search_returns_results_with_scores(
        self, mock_embed, client: AsyncClient, db: AsyncSession,
    ):
        mock_embed.side_effect = make_fake_embeddings
        token = await register_and_login(client, db)

        # Create and embed a note
        resp = await client.post("/api/notes", json={
            "title": "Searchable",
            "content": "Python programming tutorial for beginners.",
        }, headers=auth(token))
        note_id = resp.json()["id"]

        # Manually set embeddings on chunks (simulating worker)
        result = await db.execute(
            select(NoteChunk).where(NoteChunk.note_id == uuid.UUID(note_id))
        )
        chunks = result.scalars().all()
        for chunk in chunks:
            chunk.embedding = FAKE_EMBEDDING
        await db.commit()

        # Search
        resp = await client.post(
            "/api/rag/search",
            json={"query": "python tutorial", "limit": 5},
            headers=auth(token),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["results"]) >= 1
        assert data["results"][0]["note_id"] == note_id
        assert data["results"][0]["score"] is not None

    @patch("app.modules.rag.service.create_embeddings", new_callable=AsyncMock)
    async def test_search_isolates_users(
        self, mock_embed, client: AsyncClient, db: AsyncSession,
    ):
        mock_embed.side_effect = make_fake_embeddings
        token1 = await register_and_login(client, db, "user1@test.com")
        token2 = await register_and_login(client, db, "user2@test.com")

        # User1 creates a note with embeddings
        resp = await client.post("/api/notes", json={
            "title": "Secret",
            "content": "User1 private data.",
        }, headers=auth(token1))
        note_id = resp.json()["id"]

        result = await db.execute(
            select(NoteChunk).where(NoteChunk.note_id == uuid.UUID(note_id))
        )
        for chunk in result.scalars().all():
            chunk.embedding = FAKE_EMBEDDING
        await db.commit()

        # User2 searches — should find nothing
        resp = await client.post(
            "/api/rag/search",
            json={"query": "private data"},
            headers=auth(token2),
        )
        assert resp.status_code == 200
        assert len(resp.json()["results"]) == 0

    async def test_search_validation(self, client: AsyncClient, db: AsyncSession):
        token = await register_and_login(client, db)

        # Empty query
        resp = await client.post(
            "/api/rag/search",
            json={"query": ""},
            headers=auth(token),
        )
        assert resp.status_code == 422

        # Limit too high
        resp = await client.post(
            "/api/rag/search",
            json={"query": "test", "limit": 100},
            headers=auth(token),
        )
        assert resp.status_code == 422


# --- Chunking unit tests ---

class TestChunkText:
    def test_empty_text(self):
        from app.modules.rag.service import chunk_text
        assert chunk_text("") == []

    def test_short_text(self):
        from app.modules.rag.service import chunk_text
        result = chunk_text("Hello world")
        assert len(result) == 1
        assert result[0] == "Hello world"

    def test_long_text_produces_overlapping_chunks(self):
        from app.modules.rag.service import chunk_text
        # Create text longer than one chunk
        text = "word " * 500
        result = chunk_text(text)
        assert len(result) > 1
        # Verify overlap: end of first chunk should overlap with start of second
        # (since overlap_chars > 0)
        assert result[0][-10:] in result[1]
