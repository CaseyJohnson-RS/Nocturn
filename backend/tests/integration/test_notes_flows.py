"""Integration tests for notes flows."""

import uuid
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.auth.models import User

REGISTER = "/api/auth/register"
LOGIN = "/api/auth/login"
NOTES = "/api/notes"
TAGS = "/api/tags"

USER = {"email": "user@example.com", "password": "Valid1pass", "nickname": "testuser"}
USER2 = {"email": "other@example.com", "password": "Valid1pass", "nickname": "other"}


# --- Helpers ---


async def _register_confirm_login(
    client: AsyncClient,
    db: AsyncSession,
    user_data: dict[str, str] = USER,
) -> str:
    with patch("app.modules.auth.service.send_confirmation_email", new_callable=AsyncMock):
        await client.post(REGISTER, json=user_data)

    result = await db.execute(select(User).where(User.email == user_data["email"]))
    user: User = result.scalar_one()
    user.is_email_confirmed = True
    await db.commit()

    resp = await client.post(
        LOGIN,
        json={
            "email": user_data["email"],
            "password": user_data["password"],
        },
    )
    return resp.json()["access_token"]


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _create_note(
    client: AsyncClient,
    token: str,
    title: str = "Test Note",
    content: str = "Some content",
    tag_ids: list[str] | None = None,
) -> Any:
    with patch("app.modules.rag.service.RAGRepository.enqueue", new_callable=AsyncMock):
        resp = await client.post(
            NOTES,
            json={
                "title": title,
                "content": content,
                "tag_ids": tag_ids or [],
            },
            headers=_auth(token),
        )
    assert resp.status_code == 201
    return resp.json()


async def _create_tag(client: AsyncClient, token: str, name: str) -> str:
    resp = await client.post(TAGS, json={"name": name}, headers=_auth(token))
    assert resp.status_code == 201
    return resp.json()["id"]


# --- CRUD flow ---


class TestNotesCRUD:
    @pytest.mark.anyio()
    async def test_create_and_get(self, client: AsyncClient, db: AsyncSession) -> None:
        token = await _register_confirm_login(client, db)

        note = await _create_note(client, token, title="My Note", content="Hello")

        assert note["title"] == "My Note"
        assert note["content"] == "Hello"
        assert note["version"] == 1

        resp = await client.get(f"{NOTES}/{note['id']}", headers=_auth(token))
        assert resp.status_code == 200
        assert resp.json()["title"] == "My Note"

    @pytest.mark.anyio()
    async def test_list_notes(self, client: AsyncClient, db: AsyncSession) -> None:
        token = await _register_confirm_login(client, db)

        await _create_note(client, token, title="First")
        await _create_note(client, token, title="Second")

        resp = await client.get(NOTES, headers=_auth(token))

        assert resp.status_code == 200
        assert resp.json()["total"] == 2
        assert len(resp.json()["items"]) == 2

    @pytest.mark.anyio()
    async def test_list_pagination(self, client: AsyncClient, db: AsyncSession) -> None:
        token = await _register_confirm_login(client, db)

        for i in range(5):
            await _create_note(client, token, title=f"Note {i}")

        resp = await client.get(NOTES, params={"limit": 2, "offset": 0}, headers=_auth(token))
        assert len(resp.json()["items"]) == 2
        assert resp.json()["total"] == 5

        resp = await client.get(NOTES, params={"limit": 2, "offset": 4}, headers=_auth(token))
        assert len(resp.json()["items"]) == 1

    @pytest.mark.anyio()
    async def test_update_note(self, client: AsyncClient, db: AsyncSession) -> None:
        token = await _register_confirm_login(client, db)
        note = await _create_note(client, token)

        with patch("app.modules.rag.service.RAGRepository.enqueue", new_callable=AsyncMock):
            resp = await client.put(
                f"{NOTES}/{note['id']}",
                json={
                    "title": "Updated",
                    "version": note["version"],
                },
                headers=_auth(token),
            )

        assert resp.status_code == 200
        assert resp.json()["title"] == "Updated"
        assert resp.json()["version"] == note["version"] + 1

    @pytest.mark.anyio()
    async def test_update_partial(self, client: AsyncClient, db: AsyncSession) -> None:
        token = await _register_confirm_login(client, db)
        note = await _create_note(client, token, title="Keep", content="Original")

        with patch("app.modules.rag.service.RAGRepository.enqueue", new_callable=AsyncMock):
            resp = await client.put(
                f"{NOTES}/{note['id']}",
                json={
                    "content": "Changed",
                    "version": note["version"],
                },
                headers=_auth(token),
            )

        assert resp.status_code == 200
        assert resp.json()["title"] == "Keep"
        assert resp.json()["content"] == "Changed"


# --- Version conflict ---


class TestVersionConflict:
    @pytest.mark.anyio()
    async def test_stale_version_rejected(self, client: AsyncClient, db: AsyncSession) -> None:
        token = await _register_confirm_login(client, db)
        note = await _create_note(client, token)

        with patch("app.modules.rag.service.RAGRepository.enqueue", new_callable=AsyncMock):
            await client.put(
                f"{NOTES}/{note['id']}",
                json={
                    "title": "V2",
                    "version": note["version"],
                },
                headers=_auth(token),
            )

            resp = await client.put(
                f"{NOTES}/{note['id']}",
                json={
                    "title": "V2 again",
                    "version": note["version"],  # stale
                },
                headers=_auth(token),
            )

        assert resp.status_code == 409


# --- Soft delete / restore / hard delete ---


class TestDeleteFlow:
    @pytest.mark.anyio()
    async def test_soft_delete_and_restore(self, client: AsyncClient, db: AsyncSession) -> None:
        token = await _register_confirm_login(client, db)
        note = await _create_note(client, token)

        with (
            patch("app.modules.rag.service.RAGRepository.enqueue", new_callable=AsyncMock),
            patch(
                "app.modules.rag.service.RAGRepository.delete_chunks_for_note",
                new_callable=AsyncMock,
            ),
            patch("app.modules.rag.service.RAGRepository.remove_task", new_callable=AsyncMock),
        ):
            # Soft delete
            resp = await client.delete(f"{NOTES}/{note['id']}", headers=_auth(token))
            assert resp.status_code == 204

            # Not in active list
            resp = await client.get(NOTES, headers=_auth(token))
            assert resp.json()["total"] == 0

            # In deleted list
            resp = await client.get(NOTES, params={"deleted": True}, headers=_auth(token))
            assert resp.json()["total"] == 1

            # Restore
            resp = await client.post(f"{NOTES}/{note['id']}/restore", headers=_auth(token))
            assert resp.status_code == 200
            assert resp.json()["deleted_at"] is None

        # Back in active list
        resp = await client.get(NOTES, headers=_auth(token))
        assert resp.json()["total"] == 1

    @pytest.mark.anyio()
    async def test_hard_delete(self, client: AsyncClient, db: AsyncSession) -> None:
        token = await _register_confirm_login(client, db)
        note = await _create_note(client, token)

        with (
            patch("app.modules.rag.service.RAGRepository.enqueue", new_callable=AsyncMock),
            patch(
                "app.modules.rag.service.RAGRepository.delete_chunks_for_note",
                new_callable=AsyncMock,
            ),
            patch("app.modules.rag.service.RAGRepository.remove_task", new_callable=AsyncMock),
        ):
            # Must soft delete first
            await client.delete(f"{NOTES}/{note['id']}", headers=_auth(token))

            # Hard delete
            resp = await client.delete(
                f"{NOTES}/{note['id']}",
                params={"permanent": True},
                headers=_auth(token),
            )
            assert resp.status_code == 204

        # Gone from deleted list
        resp = await client.get(NOTES, params={"deleted": True}, headers=_auth(token))
        assert resp.json()["total"] == 0

        # Gone completely
        resp = await client.get(f"{NOTES}/{note['id']}", headers=_auth(token))
        assert resp.status_code == 404

    @pytest.mark.anyio()
    async def test_hard_delete_active_note_fails(
        self,
        client: AsyncClient,
        db: AsyncSession,
    ) -> None:
        token = await _register_confirm_login(client, db)
        note = await _create_note(client, token)

        resp = await client.delete(
            f"{NOTES}/{note['id']}",
            params={"permanent": True},
            headers=_auth(token),
        )
        assert resp.status_code == 404


# --- Tags ---


class TestNoteTags:
    @pytest.mark.anyio()
    async def test_create_with_tags(self, client: AsyncClient, db: AsyncSession) -> None:
        token = await _register_confirm_login(client, db)
        tag_id = await _create_tag(client, token, "work")

        note = await _create_note(client, token, tag_ids=[tag_id])

        assert len(note["tags"]) == 1
        assert note["tags"][0]["name"] == "work"

    @pytest.mark.anyio()
    async def test_update_tags(self, client: AsyncClient, db: AsyncSession) -> None:
        token = await _register_confirm_login(client, db)
        tag1 = await _create_tag(client, token, "work")
        tag2 = await _create_tag(client, token, "personal")

        note = await _create_note(client, token, tag_ids=[tag1])

        resp = await client.put(
            f"{NOTES}/{note['id']}/tags",
            json={"tag_ids": [tag2]},
            headers=_auth(token),
        )

        assert resp.status_code == 200
        assert len(resp.json()["tags"]) == 1
        assert resp.json()["tags"][0]["name"] == "personal"

    @pytest.mark.anyio()
    async def test_clear_tags(self, client: AsyncClient, db: AsyncSession) -> None:
        token = await _register_confirm_login(client, db)
        tag_id = await _create_tag(client, token, "work")
        note = await _create_note(client, token, tag_ids=[tag_id])

        resp = await client.put(
            f"{NOTES}/{note['id']}/tags",
            json={"tag_ids": []},
            headers=_auth(token),
        )

        assert resp.status_code == 200
        assert resp.json()["tags"] == []

    @pytest.mark.anyio()
    async def test_invalid_tag_id(self, client: AsyncClient, db: AsyncSession) -> None:
        token = await _register_confirm_login(client, db)
        note = await _create_note(client, token)

        resp = await client.put(
            f"{NOTES}/{note['id']}/tags",
            json={"tag_ids": [str(uuid.uuid4())]},
            headers=_auth(token),
        )

        assert resp.status_code == 404


# --- Batch ---


class TestBatchGet:
    @pytest.mark.anyio()
    async def test_success(self, client: AsyncClient, db: AsyncSession) -> None:
        token = await _register_confirm_login(client, db)
        n1 = await _create_note(client, token, title="A")
        n2 = await _create_note(client, token, title="B")

        resp = await client.post(
            f"{NOTES}/batch",
            json={"note_ids": [n1["id"], n2["id"]]},
            headers=_auth(token),
        )

        assert resp.status_code == 200
        assert len(resp.json()["items"]) == 2

    @pytest.mark.anyio()
    async def test_empty(self, client: AsyncClient, db: AsyncSession) -> None:
        token = await _register_confirm_login(client, db)

        resp = await client.post(
            f"{NOTES}/batch",
            json={"note_ids": []},
            headers=_auth(token),
        )

        assert resp.status_code == 200
        assert resp.json()["items"] == []


# --- Isolation ---


class TestIsolation:
    @pytest.mark.anyio()
    async def test_user_cannot_see_other_users_notes(
        self,
        client: AsyncClient,
        db: AsyncSession,
    ) -> None:
        token1 = await _register_confirm_login(client, db, USER)
        token2 = await _register_confirm_login(client, db, USER2)

        note = await _create_note(client, token1, title="Private")

        # User 2 cannot get
        resp = await client.get(f"{NOTES}/{note['id']}", headers=_auth(token2))
        assert resp.status_code == 404

        # User 2 cannot see in list
        resp = await client.get(NOTES, headers=_auth(token2))
        assert resp.json()["total"] == 0

    @pytest.mark.anyio()
    async def test_user_cannot_update_other_users_notes(
        self,
        client: AsyncClient,
        db: AsyncSession,
    ) -> None:
        token1 = await _register_confirm_login(client, db, USER)
        token2 = await _register_confirm_login(client, db, USER2)

        note = await _create_note(client, token1)

        with patch("app.modules.rag.service.RAGRepository.enqueue", new_callable=AsyncMock):
            resp = await client.put(
                f"{NOTES}/{note['id']}",
                json={
                    "title": "Hacked",
                    "version": note["version"],
                },
                headers=_auth(token2),
            )

        assert resp.status_code == 404

    @pytest.mark.anyio()
    async def test_user_cannot_delete_other_users_notes(
        self,
        client: AsyncClient,
        db: AsyncSession,
    ) -> None:
        token1 = await _register_confirm_login(client, db, USER)
        token2 = await _register_confirm_login(client, db, USER2)

        note = await _create_note(client, token1)

        resp = await client.delete(f"{NOTES}/{note['id']}", headers=_auth(token2))
        assert resp.status_code == 404


# --- Auth ---


class TestUnauthorized:
    @pytest.mark.anyio()
    async def test_requires_auth(self, client: AsyncClient) -> None:
        resp = await client.get(NOTES)
        assert resp.status_code == 401
