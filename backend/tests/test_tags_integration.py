"""Integration tests for the tags module."""

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


# --- Create ---

class TestCreateTag:
    async def test_create_tag(self, client: AsyncClient, db: AsyncSession):
        token = await register_and_login(client, db)
        resp = await client.post("/api/tags", json={"name": "Work"}, headers=auth(token))
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "Work"
        assert "id" in data

    async def test_create_tag_trimmed(self, client: AsyncClient, db: AsyncSession):
        token = await register_and_login(client, db)
        resp = await client.post("/api/tags", json={"name": "  Trimmed  "}, headers=auth(token))
        assert resp.status_code == 201
        assert resp.json()["name"] == "Trimmed"

    async def test_create_tag_cyrillic(self, client: AsyncClient, db: AsyncSession):
        token = await register_and_login(client, db)
        resp = await client.post("/api/tags", json={"name": "Работа"}, headers=auth(token))
        assert resp.status_code == 201
        assert resp.json()["name"] == "Работа"

    async def test_create_duplicate_case_insensitive(self, client: AsyncClient, db: AsyncSession):
        token = await register_and_login(client, db)
        await client.post("/api/tags", json={"name": "Work"}, headers=auth(token))
        resp = await client.post("/api/tags", json={"name": "work"}, headers=auth(token))
        assert resp.status_code == 409

    async def test_create_tag_invalid_chars(self, client: AsyncClient, db: AsyncSession):
        token = await register_and_login(client, db)
        resp = await client.post("/api/tags", json={"name": "bad@name!"}, headers=auth(token))
        assert resp.status_code == 400

    async def test_create_tag_empty_name(self, client: AsyncClient, db: AsyncSession):
        token = await register_and_login(client, db)
        resp = await client.post("/api/tags", json={"name": ""}, headers=auth(token))
        assert resp.status_code == 422

    async def test_create_tag_unauthenticated(self, client: AsyncClient):
        resp = await client.post("/api/tags", json={"name": "Work"})
        assert resp.status_code == 401


# --- List ---

class TestListTags:
    async def test_list_tags(self, client: AsyncClient, db: AsyncSession):
        token = await register_and_login(client, db)
        await client.post("/api/tags", json={"name": "Alpha"}, headers=auth(token))
        await client.post("/api/tags", json={"name": "Beta"}, headers=auth(token))

        resp = await client.get("/api/tags", headers=auth(token))
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2
        assert len(data["items"]) == 2

    async def test_list_tags_search(self, client: AsyncClient, db: AsyncSession):
        token = await register_and_login(client, db)
        await client.post("/api/tags", json={"name": "Work"}, headers=auth(token))
        await client.post("/api/tags", json={"name": "Personal"}, headers=auth(token))

        resp = await client.get("/api/tags", params={"search": "wor"}, headers=auth(token))
        assert resp.json()["total"] == 1
        assert resp.json()["items"][0]["name"] == "Work"

    async def test_list_tags_isolation(self, client: AsyncClient, db: AsyncSession):
        token1 = await register_and_login(client, db, "user1@test.com")
        token2 = await register_and_login(client, db, "user2@test.com")
        await client.post("/api/tags", json={"name": "Private"}, headers=auth(token1))

        resp = await client.get("/api/tags", headers=auth(token2))
        assert resp.json()["total"] == 0


# --- Get ---

class TestGetTag:
    async def test_get_tag(self, client: AsyncClient, db: AsyncSession):
        token = await register_and_login(client, db)
        create_resp = await client.post("/api/tags", json={"name": "Work"}, headers=auth(token))
        tag_id = create_resp.json()["id"]

        resp = await client.get(f"/api/tags/{tag_id}", headers=auth(token))
        assert resp.status_code == 200
        assert resp.json()["name"] == "Work"

    async def test_get_tag_not_found(self, client: AsyncClient, db: AsyncSession):
        token = await register_and_login(client, db)
        resp = await client.get("/api/tags/00000000-0000-0000-0000-000000000000", headers=auth(token))
        assert resp.status_code == 404


# --- Update ---

class TestUpdateTag:
    async def test_rename_tag(self, client: AsyncClient, db: AsyncSession):
        token = await register_and_login(client, db)
        create_resp = await client.post("/api/tags", json={"name": "Old"}, headers=auth(token))
        tag_id = create_resp.json()["id"]

        resp = await client.put(f"/api/tags/{tag_id}", json={"name": "New"}, headers=auth(token))
        assert resp.status_code == 200
        assert resp.json()["name"] == "New"

    async def test_rename_to_existing(self, client: AsyncClient, db: AsyncSession):
        token = await register_and_login(client, db)
        await client.post("/api/tags", json={"name": "Alpha"}, headers=auth(token))
        create_resp = await client.post("/api/tags", json={"name": "Beta"}, headers=auth(token))
        tag_id = create_resp.json()["id"]

        resp = await client.put(f"/api/tags/{tag_id}", json={"name": "alpha"}, headers=auth(token))
        assert resp.status_code == 409


# --- Delete ---

class TestDeleteTag:
    async def test_delete_tag(self, client: AsyncClient, db: AsyncSession):
        token = await register_and_login(client, db)
        create_resp = await client.post("/api/tags", json={"name": "ToDelete"}, headers=auth(token))
        tag_id = create_resp.json()["id"]

        resp = await client.delete(f"/api/tags/{tag_id}", headers=auth(token))
        assert resp.status_code == 204

        resp = await client.get(f"/api/tags/{tag_id}", headers=auth(token))
        assert resp.status_code == 404

    async def test_delete_nonexistent(self, client: AsyncClient, db: AsyncSession):
        token = await register_and_login(client, db)
        resp = await client.delete("/api/tags/00000000-0000-0000-0000-000000000000", headers=auth(token))
        assert resp.status_code == 404
