"""Integration tests for tags flows."""

import uuid
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.auth.models import User

REGISTER = "/api/auth/register"
LOGIN = "/api/auth/login"
TAGS = "/api/tags"

USER = {"email": "user@example.com", "password": "Valid1pass", "nickname": "testuser"}
USER2 = {"email": "other@example.com", "password": "Valid1pass", "nickname": "other"}


# --- Helpers ---


async def _register_confirm_login(
    client: AsyncClient, db: AsyncSession, user_data: dict[str, str] = USER,
) -> str:
    with patch("app.modules.auth.service.send_confirmation_email", new_callable=AsyncMock):
        await client.post(REGISTER, json=user_data)

    result = await db.execute(select(User).where(User.email == user_data["email"]))
    user: User = result.scalar_one()
    user.is_email_confirmed = True
    await db.commit()

    resp = await client.post(LOGIN, json={
        "email": user_data["email"],
        "password": user_data["password"],
    })
    return resp.json()["access_token"]


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _create_tag(client: AsyncClient, token: str, name: str) -> dict:
    resp = await client.post(TAGS, json={"name": name}, headers=_auth(token))
    assert resp.status_code == 201
    return resp.json()


# --- CRUD ---


class TestTagsCRUD:
    @pytest.mark.anyio()
    async def test_create_and_get(self, client: AsyncClient, db: AsyncSession) -> None:
        token = await _register_confirm_login(client, db)

        tag = await _create_tag(client, token, "work")

        assert tag["name"] == "work"

        resp = await client.get(f"{TAGS}/{tag['id']}", headers=_auth(token))
        assert resp.status_code == 200
        assert resp.json()["name"] == "work"

    @pytest.mark.anyio()
    async def test_list_tags(self, client: AsyncClient, db: AsyncSession) -> None:
        token = await _register_confirm_login(client, db)

        await _create_tag(client, token, "work")
        await _create_tag(client, token, "personal")

        resp = await client.get(TAGS, headers=_auth(token))

        assert resp.status_code == 200
        assert resp.json()["total"] == 2
        assert len(resp.json()["items"]) == 2

    @pytest.mark.anyio()
    async def test_list_with_search(self, client: AsyncClient, db: AsyncSession) -> None:
        token = await _register_confirm_login(client, db)

        await _create_tag(client, token, "work")
        await _create_tag(client, token, "personal")

        resp = await client.get(TAGS, params={"search": "work"}, headers=_auth(token))

        assert resp.status_code == 200
        assert resp.json()["total"] == 1
        assert resp.json()["items"][0]["name"] == "work"

    @pytest.mark.anyio()
    async def test_list_pagination(self, client: AsyncClient, db: AsyncSession) -> None:
        token = await _register_confirm_login(client, db)

        for i in range(5):
            await _create_tag(client, token, f"tag-{i}")

        resp = await client.get(TAGS, params={"limit": 2, "offset": 0}, headers=_auth(token))
        assert len(resp.json()["items"]) == 2
        assert resp.json()["total"] == 5

    @pytest.mark.anyio()
    async def test_update_tag(self, client: AsyncClient, db: AsyncSession) -> None:
        token = await _register_confirm_login(client, db)
        tag = await _create_tag(client, token, "old")

        resp = await client.put(f"{TAGS}/{tag['id']}", json={"name": "new"}, headers=_auth(token))

        assert resp.status_code == 200
        assert resp.json()["name"] == "new"

        # Verify via get
        resp = await client.get(f"{TAGS}/{tag['id']}", headers=_auth(token))
        assert resp.json()["name"] == "new"

    @pytest.mark.anyio()
    async def test_delete_tag(self, client: AsyncClient, db: AsyncSession) -> None:
        token = await _register_confirm_login(client, db)
        tag = await _create_tag(client, token, "to-delete")

        resp = await client.delete(f"{TAGS}/{tag['id']}", headers=_auth(token))
        assert resp.status_code == 204

        resp = await client.get(f"{TAGS}/{tag['id']}", headers=_auth(token))
        assert resp.status_code == 404

        resp = await client.get(TAGS, headers=_auth(token))
        assert resp.json()["total"] == 0


# --- Duplicates ---


class TestDuplicates:
    @pytest.mark.anyio()
    async def test_duplicate_name_rejected(self, client: AsyncClient, db: AsyncSession) -> None:
        token = await _register_confirm_login(client, db)

        await _create_tag(client, token, "work")
        resp = await client.post(TAGS, json={"name": "work"}, headers=_auth(token))

        assert resp.status_code == 409

    @pytest.mark.anyio()
    async def test_rename_to_existing_rejected(self, client: AsyncClient, db: AsyncSession) -> None:
        token = await _register_confirm_login(client, db)

        await _create_tag(client, token, "work")
        tag2 = await _create_tag(client, token, "personal")

        resp = await client.put(
            f"{TAGS}/{tag2['id']}", json={"name": "work"}, headers=_auth(token),
        )

        assert resp.status_code == 409

    @pytest.mark.anyio()
    async def test_rename_to_same_name_allowed(
        self, client: AsyncClient, db: AsyncSession,
    ) -> None:
        token = await _register_confirm_login(client, db)
        tag = await _create_tag(client, token, "work")

        resp = await client.put(
            f"{TAGS}/{tag['id']}", json={"name": "work"}, headers=_auth(token),
        )

        assert resp.status_code == 200

    @pytest.mark.anyio()
    async def test_same_name_different_users_allowed(
        self, client: AsyncClient, db: AsyncSession,
    ) -> None:
        token1 = await _register_confirm_login(client, db, USER)
        token2 = await _register_confirm_login(client, db, USER2)

        await _create_tag(client, token1, "work")
        resp = await client.post(TAGS, json={"name": "work"}, headers=_auth(token2))

        assert resp.status_code == 201


# --- Isolation ---


class TestIsolation:
    @pytest.mark.anyio()
    async def test_user_cannot_see_other_users_tags(
        self, client: AsyncClient, db: AsyncSession,
    ) -> None:
        token1 = await _register_confirm_login(client, db, USER)
        token2 = await _register_confirm_login(client, db, USER2)

        tag = await _create_tag(client, token1, "private")

        resp = await client.get(f"{TAGS}/{tag['id']}", headers=_auth(token2))
        assert resp.status_code == 404

        resp = await client.get(TAGS, headers=_auth(token2))
        assert resp.json()["total"] == 0

    @pytest.mark.anyio()
    async def test_user_cannot_update_other_users_tags(
        self, client: AsyncClient, db: AsyncSession,
    ) -> None:
        token1 = await _register_confirm_login(client, db, USER)
        token2 = await _register_confirm_login(client, db, USER2)

        tag = await _create_tag(client, token1, "private")

        resp = await client.put(
            f"{TAGS}/{tag['id']}", json={"name": "hacked"}, headers=_auth(token2),
        )
        assert resp.status_code == 404

    @pytest.mark.anyio()
    async def test_user_cannot_delete_other_users_tags(
        self, client: AsyncClient, db: AsyncSession,
    ) -> None:
        token1 = await _register_confirm_login(client, db, USER)
        token2 = await _register_confirm_login(client, db, USER2)

        tag = await _create_tag(client, token1, "private")

        resp = await client.delete(f"{TAGS}/{tag['id']}", headers=_auth(token2))
        assert resp.status_code == 404


# --- Not found ---


class TestNotFound:
    @pytest.mark.anyio()
    async def test_get_nonexistent(self, client: AsyncClient, db: AsyncSession) -> None:
        token = await _register_confirm_login(client, db)

        resp = await client.get(f"{TAGS}/{uuid.uuid4()}", headers=_auth(token))
        assert resp.status_code == 404

    @pytest.mark.anyio()
    async def test_update_nonexistent(self, client: AsyncClient, db: AsyncSession) -> None:
        token = await _register_confirm_login(client, db)

        resp = await client.put(
            f"{TAGS}/{uuid.uuid4()}", json={"name": "new"}, headers=_auth(token),
        )
        assert resp.status_code == 404

    @pytest.mark.anyio()
    async def test_delete_nonexistent(self, client: AsyncClient, db: AsyncSession) -> None:
        token = await _register_confirm_login(client, db)

        resp = await client.delete(f"{TAGS}/{uuid.uuid4()}", headers=_auth(token))
        assert resp.status_code == 404


# --- Auth ---


class TestUnauthorized:
    @pytest.mark.anyio()
    async def test_requires_auth(self, client: AsyncClient) -> None:
        resp = await client.get(TAGS)
        assert resp.status_code == 401