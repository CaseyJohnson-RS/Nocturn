"""Integration tests for the notes module."""

import pytest
from httpx import AsyncClient
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.auth.models import User


# --- Helpers ---

async def register_and_login(client: AsyncClient, db: AsyncSession, email="user@test.com") -> str:
    """Register, confirm, login, return access token."""
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


async def create_tag(client: AsyncClient, token: str, name: str) -> str:
    resp = await client.post("/api/tags", json={"name": name}, headers=auth(token))
    return resp.json()["id"]


async def create_note(
    client: AsyncClient, token: str,
    title="Test Note", content="Test content", tag_ids=None,
) -> dict:
    resp = await client.post("/api/notes", json={
        "title": title,
        "content": content,
        "tag_ids": tag_ids or [],
    }, headers=auth(token))
    return resp.json()


# --- Create ---

class TestCreateNote:
    async def test_create_note(self, client: AsyncClient, db: AsyncSession):
        token = await register_and_login(client, db)
        resp = await client.post("/api/notes", json={
            "title": "My Note",
            "content": "Hello world",
        }, headers=auth(token))
        assert resp.status_code == 201
        data = resp.json()
        assert data["title"] == "My Note"
        assert data["content"] == "Hello world"
        assert data["version"] == 1
        assert data["deleted_at"] is None
        assert data["tags"] == []

    async def test_create_note_empty(self, client: AsyncClient, db: AsyncSession):
        token = await register_and_login(client, db)
        resp = await client.post("/api/notes", json={}, headers=auth(token))
        assert resp.status_code == 201
        data = resp.json()
        assert data["title"] is None
        assert data["content"] is None

    async def test_create_note_with_tags(self, client: AsyncClient, db: AsyncSession):
        token = await register_and_login(client, db)
        tag_id = await create_tag(client, token, "Work")
        resp = await client.post("/api/notes", json={
            "title": "Tagged",
            "content": "Content",
            "tag_ids": [tag_id],
        }, headers=auth(token))
        assert resp.status_code == 201
        assert len(resp.json()["tags"]) == 1
        assert resp.json()["tags"][0]["name"] == "Work"

    async def test_create_note_sanitizes_html(self, client: AsyncClient, db: AsyncSession):
        token = await register_and_login(client, db)
        resp = await client.post("/api/notes", json={
            "title": "Clean",
            "content": "<script>alert('xss')</script><b>bold</b>",
        }, headers=auth(token))
        assert resp.status_code == 201
        assert "<script>" not in resp.json()["content"]
        assert "<b>bold</b>" in resp.json()["content"]

    async def test_create_note_unauthenticated(self, client: AsyncClient):
        resp = await client.post("/api/notes", json={"title": "X"})
        assert resp.status_code == 401

    async def test_create_note_too_long_title(self, client: AsyncClient, db: AsyncSession):
        token = await register_and_login(client, db)
        resp = await client.post("/api/notes", json={
            "title": "x" * 201,
        }, headers=auth(token))
        assert resp.status_code == 422


# --- Get ---

class TestGetNote:
    async def test_get_note(self, client: AsyncClient, db: AsyncSession):
        token = await register_and_login(client, db)
        note = await create_note(client, token)

        resp = await client.get(f"/api/notes/{note['id']}", headers=auth(token))
        assert resp.status_code == 200
        assert resp.json()["title"] == "Test Note"

    async def test_get_note_not_found(self, client: AsyncClient, db: AsyncSession):
        token = await register_and_login(client, db)
        resp = await client.get("/api/notes/00000000-0000-0000-0000-000000000000", headers=auth(token))
        assert resp.status_code == 404

    async def test_get_note_other_user(self, client: AsyncClient, db: AsyncSession):
        token1 = await register_and_login(client, db, "user1@test.com")
        token2 = await register_and_login(client, db, "user2@test.com")
        note = await create_note(client, token1)

        resp = await client.get(f"/api/notes/{note['id']}", headers=auth(token2))
        assert resp.status_code == 404


# --- List ---

class TestListNotes:
    async def test_list_notes(self, client: AsyncClient, db: AsyncSession):
        token = await register_and_login(client, db)
        await create_note(client, token, title="First")
        await create_note(client, token, title="Second")

        resp = await client.get("/api/notes", headers=auth(token))
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2
        assert len(data["items"]) == 2

    async def test_list_notes_excludes_deleted(self, client: AsyncClient, db: AsyncSession):
        token = await register_and_login(client, db)
        note = await create_note(client, token)
        await client.delete(f"/api/notes/{note['id']}", headers=auth(token))

        resp = await client.get("/api/notes", headers=auth(token))
        assert resp.json()["total"] == 0

    async def test_list_trash(self, client: AsyncClient, db: AsyncSession):
        token = await register_and_login(client, db)
        note = await create_note(client, token)
        await client.delete(f"/api/notes/{note['id']}", headers=auth(token))

        resp = await client.get("/api/notes", params={"deleted": "true"}, headers=auth(token))
        assert resp.json()["total"] == 1

    async def test_list_notes_search(self, client: AsyncClient, db: AsyncSession):
        token = await register_and_login(client, db)
        await create_note(client, token, title="Python Guide", content="Learn Python")
        await create_note(client, token, title="Cooking", content="Recipes")

        resp = await client.get("/api/notes", params={"search": "python"}, headers=auth(token))
        assert resp.json()["total"] == 1

    async def test_list_notes_filter_by_tag(self, client: AsyncClient, db: AsyncSession):
        token = await register_and_login(client, db)
        tag_id = await create_tag(client, token, "Work")
        await create_note(client, token, title="Tagged", tag_ids=[tag_id])
        await create_note(client, token, title="Untagged")

        resp = await client.get("/api/notes", params={"tag_ids": tag_id}, headers=auth(token))
        assert resp.json()["total"] == 1
        assert resp.json()["items"][0]["title"] == "Tagged"

    async def test_list_pagination(self, client: AsyncClient, db: AsyncSession):
        token = await register_and_login(client, db)
        for i in range(5):
            await create_note(client, token, title=f"Note {i}")

        resp = await client.get("/api/notes", params={"limit": 2, "offset": 0}, headers=auth(token))
        data = resp.json()
        assert data["total"] == 5
        assert len(data["items"]) == 2
        assert data["limit"] == 2
        assert data["offset"] == 0


# --- Update ---

class TestUpdateNote:
    async def test_update_note(self, client: AsyncClient, db: AsyncSession):
        token = await register_and_login(client, db)
        note = await create_note(client, token)

        resp = await client.put(f"/api/notes/{note['id']}", json={
            "title": "Updated Title",
            "content": "Updated content",
            "version": 1,
        }, headers=auth(token))
        assert resp.status_code == 200
        data = resp.json()
        assert data["title"] == "Updated Title"
        assert data["version"] == 2

    async def test_update_version_conflict(self, client: AsyncClient, db: AsyncSession):
        token = await register_and_login(client, db)
        note = await create_note(client, token)

        # First update succeeds
        await client.put(f"/api/notes/{note['id']}", json={
            "title": "V2", "content": "C2", "version": 1,
        }, headers=auth(token))

        # Second update with stale version fails
        resp = await client.put(f"/api/notes/{note['id']}", json={
            "title": "V2 again", "content": "C2 again", "version": 1,
        }, headers=auth(token))
        assert resp.status_code == 409

    async def test_update_sanitizes_html(self, client: AsyncClient, db: AsyncSession):
        token = await register_and_login(client, db)
        note = await create_note(client, token)

        resp = await client.put(f"/api/notes/{note['id']}", json={
            "title": "Clean",
            "content": "<script>bad</script>ok",
            "version": 1,
        }, headers=auth(token))
        assert resp.status_code == 200
        assert "<script>" not in resp.json()["content"]

    async def test_update_not_found(self, client: AsyncClient, db: AsyncSession):
        token = await register_and_login(client, db)
        resp = await client.put("/api/notes/00000000-0000-0000-0000-000000000000", json={
            "title": "X", "content": "Y", "version": 1,
        }, headers=auth(token))
        assert resp.status_code == 404


# --- Delete ---

class TestDeleteNote:
    async def test_soft_delete(self, client: AsyncClient, db: AsyncSession):
        token = await register_and_login(client, db)
        note = await create_note(client, token)

        resp = await client.delete(f"/api/notes/{note['id']}", headers=auth(token))
        assert resp.status_code == 204

        # Should not appear in active list
        resp = await client.get("/api/notes", headers=auth(token))
        assert resp.json()["total"] == 0

        # Should appear in trash
        resp = await client.get("/api/notes", params={"deleted": "true"}, headers=auth(token))
        assert resp.json()["total"] == 1

    async def test_hard_delete(self, client: AsyncClient, db: AsyncSession):
        token = await register_and_login(client, db)
        note = await create_note(client, token)

        # Soft delete first
        await client.delete(f"/api/notes/{note['id']}", headers=auth(token))

        # Then hard delete
        resp = await client.delete(
            f"/api/notes/{note['id']}", params={"permanent": "true"}, headers=auth(token)
        )
        assert resp.status_code == 204

        # Should not appear in trash either
        resp = await client.get("/api/notes", params={"deleted": "true"}, headers=auth(token))
        assert resp.json()["total"] == 0

    async def test_hard_delete_active_note_fails(self, client: AsyncClient, db: AsyncSession):
        """Can only hard-delete notes that are already in trash."""
        token = await register_and_login(client, db)
        note = await create_note(client, token)

        resp = await client.delete(
            f"/api/notes/{note['id']}", params={"permanent": "true"}, headers=auth(token)
        )
        assert resp.status_code == 404


# --- Restore ---

class TestRestoreNote:
    async def test_restore_note(self, client: AsyncClient, db: AsyncSession):
        token = await register_and_login(client, db)
        note = await create_note(client, token)

        await client.delete(f"/api/notes/{note['id']}", headers=auth(token))

        resp = await client.post(f"/api/notes/{note['id']}/restore", headers=auth(token))
        assert resp.status_code == 200
        assert resp.json()["deleted_at"] is None

    async def test_restore_active_note_fails(self, client: AsyncClient, db: AsyncSession):
        token = await register_and_login(client, db)
        note = await create_note(client, token)

        resp = await client.post(f"/api/notes/{note['id']}/restore", headers=auth(token))
        assert resp.status_code == 404


# --- Tags on notes ---

class TestNoteTags:
    async def test_update_note_tags(self, client: AsyncClient, db: AsyncSession):
        token = await register_and_login(client, db)
        note = await create_note(client, token)
        tag_id = await create_tag(client, token, "Work")

        resp = await client.put(
            f"/api/notes/{note['id']}/tags",
            json={"tag_ids": [tag_id]},
            headers=auth(token),
        )
        assert resp.status_code == 200
        assert len(resp.json()["tags"]) == 1

    async def test_clear_note_tags(self, client: AsyncClient, db: AsyncSession):
        token = await register_and_login(client, db)
        tag_id = await create_tag(client, token, "Work")
        note = await create_note(client, token, tag_ids=[tag_id])

        resp = await client.put(
            f"/api/notes/{note['id']}/tags",
            json={"tag_ids": []},
            headers=auth(token),
        )
        assert resp.status_code == 200
        assert resp.json()["tags"] == []

    async def test_tag_deletion_detaches_from_notes(self, client: AsyncClient, db: AsyncSession):
        token = await register_and_login(client, db)
        tag_id = await create_tag(client, token, "Temp")
        note = await create_note(client, token, tag_ids=[tag_id])

        await client.delete(f"/api/tags/{tag_id}", headers=auth(token))

        resp = await client.get(f"/api/notes/{note['id']}", headers=auth(token))
        assert resp.json()["tags"] == []


# --- Batch ---

class TestBatchGetNotes:
    async def test_batch_get(self, client: AsyncClient, db: AsyncSession):
        token = await register_and_login(client, db)
        n1 = await create_note(client, token, title="One")
        n2 = await create_note(client, token, title="Two")

        resp = await client.post("/api/notes/batch", json={
            "note_ids": [n1["id"], n2["id"]],
        }, headers=auth(token))
        assert resp.status_code == 200
        assert len(resp.json()["items"]) == 2

    async def test_batch_ignores_other_user(self, client: AsyncClient, db: AsyncSession):
        token1 = await register_and_login(client, db, "user1@test.com")
        token2 = await register_and_login(client, db, "user2@test.com")
        note = await create_note(client, token1)

        resp = await client.post("/api/notes/batch", json={
            "note_ids": [note["id"]],
        }, headers=auth(token2))
        assert resp.json()["items"] == []
