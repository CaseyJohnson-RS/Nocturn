"""Integration tests for the admin module."""

from httpx import AsyncClient
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.auth.models import User


# --- Helpers ---

async def register_and_login(
    client: AsyncClient, db: AsyncSession, email="user@test.com", role="user"
) -> str:
    """Register, confirm, optionally promote, login, return access token."""
    await client.post("/api/auth/register", json={
        "email": email,
        "password": "ValidPass1",
        "nickname": email.split("@")[0],
    })
    await db.execute(
        update(User).where(User.email == email).values(
            is_email_confirmed=True, role=role
        )
    )
    await db.commit()
    resp = await client.post("/api/auth/login", json={
        "email": email,
        "password": "ValidPass1",
    })
    return resp.json()["access_token"]


def auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# --- List users ---

class TestListUsers:
    async def test_list_users(self, client: AsyncClient, db: AsyncSession):
        admin_token = await register_and_login(client, db, "admin@test.com", role="admin")
        await register_and_login(client, db, "user1@test.com")
        await register_and_login(client, db, "user2@test.com")

        resp = await client.get("/api/admin/users", headers=auth(admin_token))
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 3  # admin + 2 users

    async def test_list_users_search(self, client: AsyncClient, db: AsyncSession):
        admin_token = await register_and_login(client, db, "admin@test.com", role="admin")
        await register_and_login(client, db, "alice@test.com")
        await register_and_login(client, db, "bob@test.com")

        resp = await client.get(
            "/api/admin/users", params={"search": "alice"}, headers=auth(admin_token)
        )
        assert resp.json()["total"] == 1
        assert resp.json()["items"][0]["email"] == "alice@test.com"

    async def test_list_users_pagination(self, client: AsyncClient, db: AsyncSession):
        admin_token = await register_and_login(client, db, "admin@test.com", role="admin")
        await register_and_login(client, db, "user1@test.com")
        await register_and_login(client, db, "user2@test.com")
        await register_and_login(client, db, "user3@test.com")

        resp = await client.get(
            "/api/admin/users", params={"limit": 2, "offset": 0}, headers=auth(admin_token)
        )
        data = resp.json()
        assert data["total"] == 4
        assert len(data["items"]) == 2

    async def test_list_users_forbidden_for_regular_user(self, client: AsyncClient, db: AsyncSession):
        token = await register_and_login(client, db)
        resp = await client.get("/api/admin/users", headers=auth(token))
        assert resp.status_code == 403

    async def test_list_users_unauthenticated(self, client: AsyncClient):
        resp = await client.get("/api/admin/users")
        assert resp.status_code == 401


# --- Get user ---

class TestGetUser:
    async def test_get_user(self, client: AsyncClient, db: AsyncSession):
        admin_token = await register_and_login(client, db, "admin@test.com", role="admin")
        user_token = await register_and_login(client, db, "user@test.com")

        # Get user list to find user_id
        resp = await client.get(
            "/api/admin/users", params={"search": "user@test.com"}, headers=auth(admin_token)
        )
        user_id = resp.json()["items"][0]["id"]

        resp = await client.get(f"/api/admin/users/{user_id}", headers=auth(admin_token))
        assert resp.status_code == 200
        assert resp.json()["email"] == "user@test.com"

    async def test_get_user_not_found(self, client: AsyncClient, db: AsyncSession):
        admin_token = await register_and_login(client, db, "admin@test.com", role="admin")
        resp = await client.get(
            "/api/admin/users/00000000-0000-0000-0000-000000000000",
            headers=auth(admin_token),
        )
        assert resp.status_code == 404


# --- Set active ---

class TestSetActive:
    async def test_block_user(self, client: AsyncClient, db: AsyncSession):
        admin_token = await register_and_login(client, db, "admin@test.com", role="admin")
        await register_and_login(client, db, "user@test.com")

        resp = await client.get(
            "/api/admin/users", params={"search": "user@test.com"}, headers=auth(admin_token)
        )
        user_id = resp.json()["items"][0]["id"]

        resp = await client.put(
            f"/api/admin/users/{user_id}/active",
            json={"is_active": False},
            headers=auth(admin_token),
        )
        assert resp.status_code == 200
        assert resp.json()["is_active"] is False

        # Blocked user can't login
        resp = await client.post("/api/auth/login", json={
            "email": "user@test.com",
            "password": "ValidPass1",
        })
        assert resp.status_code == 401

    async def test_unblock_user(self, client: AsyncClient, db: AsyncSession):
        admin_token = await register_and_login(client, db, "admin@test.com", role="admin")
        await register_and_login(client, db, "user@test.com")

        resp = await client.get(
            "/api/admin/users", params={"search": "user@test.com"}, headers=auth(admin_token)
        )
        user_id = resp.json()["items"][0]["id"]

        # Block then unblock
        await client.put(
            f"/api/admin/users/{user_id}/active",
            json={"is_active": False},
            headers=auth(admin_token),
        )
        resp = await client.put(
            f"/api/admin/users/{user_id}/active",
            json={"is_active": True},
            headers=auth(admin_token),
        )
        assert resp.status_code == 200
        assert resp.json()["is_active"] is True

    async def test_cannot_block_self(self, client: AsyncClient, db: AsyncSession):
        admin_token = await register_and_login(client, db, "admin@test.com", role="admin")

        # Get admin's own ID
        resp = await client.get("/api/auth/me", headers=auth(admin_token))
        admin_id = resp.json()["id"]

        resp = await client.put(
            f"/api/admin/users/{admin_id}/active",
            json={"is_active": False},
            headers=auth(admin_token),
        )
        assert resp.status_code == 403


# --- Set role ---

class TestSetRole:
    async def test_promote_to_admin(self, client: AsyncClient, db: AsyncSession):
        admin_token = await register_and_login(client, db, "admin@test.com", role="admin")
        await register_and_login(client, db, "user@test.com")

        resp = await client.get(
            "/api/admin/users", params={"search": "user@test.com"}, headers=auth(admin_token)
        )
        user_id = resp.json()["items"][0]["id"]

        resp = await client.put(
            f"/api/admin/users/{user_id}/role",
            json={"role": "admin"},
            headers=auth(admin_token),
        )
        assert resp.status_code == 200
        assert resp.json()["role"] == "admin"

    async def test_demote_to_user(self, client: AsyncClient, db: AsyncSession):
        admin_token = await register_and_login(client, db, "admin@test.com", role="admin")
        await register_and_login(client, db, "admin2@test.com", role="admin")

        resp = await client.get(
            "/api/admin/users", params={"search": "admin2@test.com"}, headers=auth(admin_token)
        )
        user_id = resp.json()["items"][0]["id"]

        resp = await client.put(
            f"/api/admin/users/{user_id}/role",
            json={"role": "user"},
            headers=auth(admin_token),
        )
        assert resp.status_code == 200
        assert resp.json()["role"] == "user"

    async def test_cannot_change_own_role(self, client: AsyncClient, db: AsyncSession):
        admin_token = await register_and_login(client, db, "admin@test.com", role="admin")

        resp = await client.get("/api/auth/me", headers=auth(admin_token))
        admin_id = resp.json()["id"]

        resp = await client.put(
            f"/api/admin/users/{admin_id}/role",
            json={"role": "user"},
            headers=auth(admin_token),
        )
        assert resp.status_code == 403

    async def test_invalid_role(self, client: AsyncClient, db: AsyncSession):
        admin_token = await register_and_login(client, db, "admin@test.com", role="admin")
        await register_and_login(client, db, "user@test.com")

        resp = await client.get(
            "/api/admin/users", params={"search": "user@test.com"}, headers=auth(admin_token)
        )
        user_id = resp.json()["items"][0]["id"]

        resp = await client.put(
            f"/api/admin/users/{user_id}/role",
            json={"role": "superadmin"},
            headers=auth(admin_token),
        )
        assert resp.status_code == 422
