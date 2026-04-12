"""Integration tests for RAG flows."""

from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.app.modules.auth.models import User
from src.app.modules.rag.models import EmbeddingTask, NoteChunk
from src.app.modules.rag.service import RAGService

REGISTER = "/api/auth/register"
LOGIN = "/api/auth/login"
NOTES = "/api/notes"
SEARCH = "/api/rag/search"

USER = {"email": "user@example.com", "password": "Valid1pass", "nickname": "testuser"}

FAKE_EMBEDDING = [0.1] * 2560  # match settings.embedding_dimensions


# --- Helpers ---


async def _register_confirm_login(client: AsyncClient, db: AsyncSession) -> str:
    with patch("src.app.modules.auth.service.send_confirmation_email", new_callable=AsyncMock):
        await client.post(REGISTER, json=USER)

    result = await db.execute(select(User).where(User.email == USER["email"]))
    user: User = result.scalar_one()
    user.is_email_confirmed = True
    await db.commit()

    resp = await client.post(LOGIN, json={"email": USER["email"], "password": USER["password"]})
    return resp.json()["access_token"]


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _mock_embeddings(num: int = 1) -> list[list[float]]:
    return [FAKE_EMBEDDING] * num


# --- Index + Search flow ---


class TestIndexAndSearch:
    @pytest.mark.anyio()
    async def test_create_note_enqueues_embedding(
        self,
        client: AsyncClient,
        db: AsyncSession,
    ) -> None:
        token = await _register_confirm_login(client, db)

        with patch("src.app.modules.rag.service.create_embeddings", new_callable=AsyncMock):
            resp = await client.post(
                NOTES,
                json={
                    "title": "Test Note",
                    "content": "Some content for embedding",
                    "tag_ids": [],
                },
                headers=_auth(token),
            )

        assert resp.status_code == 201

        result = await db.execute(select(EmbeddingTask))
        task: EmbeddingTask | None = result.scalar_one_or_none()
        assert task is not None
        assert task.status == "pending"

    @pytest.mark.anyio()
    async def test_embed_and_search(
        self,
        client: AsyncClient,
        db: AsyncSession,
    ) -> None:
        token = await _register_confirm_login(client, db)

        # Create note
        with patch("src.app.modules.rag.service.create_embeddings", new_callable=AsyncMock):
            resp = await client.post(
                NOTES,
                json={
                    "title": "Machine Learning",
                    "content": "Neural networks are computational models inspired by the brain.",
                    "tag_ids": [],
                },
                headers=_auth(token),
            )

        assert resp.status_code == 201
        note_id = resp.json()["id"]

        # Simulate worker: embed the note
        from src.app.modules.rag.service import RAGService

        result = await db.execute(select(User).where(User.email == USER["email"]))
        user: User = result.scalar_one()

        with patch(
            "src.app.modules.rag.service.create_embeddings",
            new_callable=AsyncMock,
        ) as mock_embed:
            mock_embed.return_value = _mock_embeddings(1)

            svc = RAGService(db)
            await svc.embed_note(note_id, user.id)
            await db.commit()

        # Verify chunks created
        result = await db.execute(select(NoteChunk).where(NoteChunk.note_id == note_id))
        chunks = list(result.scalars().all())
        assert len(chunks) > 0

        # Search
        with patch(
            "src.app.modules.rag.service.create_embeddings",
            new_callable=AsyncMock,
        ) as mock_embed:
            mock_embed.return_value = [FAKE_EMBEDDING]

            resp = await client.post(
                SEARCH,
                json={
                    "query": "neural networks",
                },
                headers=_auth(token),
            )

        assert resp.status_code == 200
        results = resp.json()["results"]
        assert len(results) > 0
        assert results[0]["note_id"] == note_id


# --- Remove note ---


class TestRemoveFromIndex:
    @pytest.mark.anyio()
    async def test_delete_note_removes_chunks(
        self,
        client: AsyncClient,
        db: AsyncSession,
    ) -> None:
        token = await _register_confirm_login(client, db)

        # Create + embed
        with patch("src.app.modules.rag.service.create_embeddings", new_callable=AsyncMock):
            resp = await client.post(
                NOTES,
                json={
                    "title": "To Delete",
                    "content": "This note will be removed.",
                    "tag_ids": [],
                },
                headers=_auth(token),
            )

        note_id = resp.json()["id"]

        result = await db.execute(select(User).where(User.email == USER["email"]))
        user: User = result.scalar_one()

        with patch(
            "src.app.modules.rag.service.create_embeddings",
            new_callable=AsyncMock,
        ) as mock_embed:
            mock_embed.return_value = _mock_embeddings(1)

            svc = RAGService(db)
            await svc.embed_note(note_id, user.id)
            await db.commit()

        # Soft delete
        with patch("src.app.modules.rag.service.create_embeddings", new_callable=AsyncMock):
            resp = await client.delete(f"{NOTES}/{note_id}", headers=_auth(token))

        assert resp.status_code == 204

        # Chunks removed
        result = await db.execute(select(NoteChunk).where(NoteChunk.note_id == note_id))
        assert result.scalars().all() == []

        # Task removed
        result = await db.execute(select(EmbeddingTask).where(EmbeddingTask.note_id == note_id))
        assert result.scalar_one_or_none() is None


# --- Search edge cases ---


class TestSearchEdgeCases:
    @pytest.mark.anyio()
    async def test_search_no_notes(self, client: AsyncClient, db: AsyncSession) -> None:
        token = await _register_confirm_login(client, db)

        with patch(
            "src.app.modules.rag.service.create_embeddings",
            new_callable=AsyncMock,
        ) as mock_embed:
            mock_embed.return_value = [FAKE_EMBEDDING]

            resp = await client.post(SEARCH, json={"query": "anything"}, headers=_auth(token))

        assert resp.status_code == 200
        assert resp.json()["results"] == []

    @pytest.mark.anyio()
    async def test_search_unauthorized(self, client: AsyncClient) -> None:
        resp = await client.post(SEARCH, json={"query": "test"})

        assert resp.status_code == 401

    @pytest.mark.anyio()
    async def test_user_cannot_search_other_users_notes(
        self,
        client: AsyncClient,
        db: AsyncSession,
    ) -> None:
        # User 1 creates and embeds a note
        token1 = await _register_confirm_login(client, db)

        with patch("src.app.modules.rag.service.create_embeddings", new_callable=AsyncMock):
            resp = await client.post(
                NOTES,
                json={
                    "title": "Secret",
                    "content": "Private information.",
                    "tag_ids": [],
                },
                headers=_auth(token1),
            )

        note_id = resp.json()["id"]

        result = await db.execute(select(User).where(User.email == USER["email"]))
        user1: User = result.scalar_one()

        with patch(
            "src.app.modules.rag.service.create_embeddings",
            new_callable=AsyncMock,
        ) as mock_embed:
            mock_embed.return_value = _mock_embeddings(1)

            from src.app.modules.rag.service import RAGService

            svc = RAGService(db)
            await svc.embed_note(note_id, user1.id)
            await db.commit()

        # Register user 2
        user2_data = {"email": "other@example.com", "password": "Valid1pass", "nickname": "other"}
        with patch("src.app.modules.auth.service.send_confirmation_email", new_callable=AsyncMock):
            await client.post(REGISTER, json=user2_data)

        result = await db.execute(select(User).where(User.email == user2_data["email"]))
        user2: User = result.scalar_one()
        user2.is_email_confirmed = True
        await db.commit()

        resp = await client.post(
            LOGIN,
            json={
                "email": user2_data["email"],
                "password": user2_data["password"],
            },
        )
        token2 = resp.json()["access_token"]

        # User 2 searches — should not find user 1's note
        with patch(
            "src.app.modules.rag.service.create_embeddings",
            new_callable=AsyncMock,
        ) as mock_embed:
            mock_embed.return_value = [FAKE_EMBEDDING]

            resp = await client.post(
                SEARCH,
                json={
                    "query": "private information",
                },
                headers=_auth(token2),
            )

        assert resp.status_code == 200
        assert resp.json()["results"] == []
