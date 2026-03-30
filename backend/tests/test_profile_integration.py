"""Integration tests for the profile module."""

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


# --- Update nickname ---

class TestUpdateNickname:
    async def test_update_nickname(self, client: AsyncClient, db: AsyncSession):
        token = await register_and_login(client, db)
        resp = await client.put(
            "/api/profile/nickname",
            json={"nickname": "new_nick"},
            headers=auth(token),
        )
        assert resp.status_code == 200
        assert resp.json()["nickname"] == "new_nick"

    async def test_update_nickname_same(self, client: AsyncClient, db: AsyncSession):
        token = await register_and_login(client, db)
        resp = await client.put(
            "/api/profile/nickname",
            json={"nickname": "user"},
            headers=auth(token),
        )
        assert resp.status_code == 200
        assert resp.json()["nickname"] == "user"

    async def test_update_nickname_taken(self, client: AsyncClient, db: AsyncSession):
        await register_and_login(client, db, "user1@test.com")
        token2 = await register_and_login(client, db, "user2@test.com")
        resp = await client.put(
            "/api/profile/nickname",
            json={"nickname": "user1"},
            headers=auth(token2),
        )
        assert resp.status_code == 409

    async def test_update_nickname_invalid(self, client: AsyncClient, db: AsyncSession):
        token = await register_and_login(client, db)
        resp = await client.put(
            "/api/profile/nickname",
            json={"nickname": "bad name!"},
            headers=auth(token),
        )
        assert resp.status_code == 422

    async def test_update_nickname_too_short(self, client: AsyncClient, db: AsyncSession):
        token = await register_and_login(client, db)
        resp = await client.put(
            "/api/profile/nickname",
            json={"nickname": "x"},
            headers=auth(token),
        )
        assert resp.status_code == 422

    async def test_update_nickname_unauthenticated(self, client: AsyncClient):
        resp = await client.put("/api/profile/nickname", json={"nickname": "test"})
        assert resp.status_code == 401


# --- Change password ---

class TestChangePassword:
    async def test_change_password(self, client: AsyncClient, db: AsyncSession):
        token = await register_and_login(client, db)
        resp = await client.put(
            "/api/profile/password",
            json={"current_password": "ValidPass1", "new_password": "NewPass123"},
            headers=auth(token),
        )
        assert resp.status_code == 200
        assert resp.json()["message"] == "Password changed successfully"

        # Old password should no longer work
        resp = await client.post("/api/auth/login", json={
            "email": "user@test.com",
            "password": "ValidPass1",
        })
        assert resp.status_code == 401

        # New password should work
        resp = await client.post("/api/auth/login", json={
            "email": "user@test.com",
            "password": "NewPass123",
        })
        assert resp.status_code == 200

    async def test_change_password_wrong_current(self, client: AsyncClient, db: AsyncSession):
        token = await register_and_login(client, db)
        resp = await client.put(
            "/api/profile/password",
            json={"current_password": "WrongPass1", "new_password": "NewPass123"},
            headers=auth(token),
        )
        assert resp.status_code == 401

    async def test_change_password_weak_new(self, client: AsyncClient, db: AsyncSession):
        token = await register_and_login(client, db)
        resp = await client.put(
            "/api/profile/password",
            json={"current_password": "ValidPass1", "new_password": "weak"},
            headers=auth(token),
        )
        assert resp.status_code == 422  # pydantic min_length

    async def test_change_password_no_uppercase(self, client: AsyncClient, db: AsyncSession):
        token = await register_and_login(client, db)
        resp = await client.put(
            "/api/profile/password",
            json={"current_password": "ValidPass1", "new_password": "alllower1"},
            headers=auth(token),
        )
        assert resp.status_code == 400  # validation error from _validate_password

    async def test_change_password_unauthenticated(self, client: AsyncClient):
        resp = await client.put("/api/profile/password", json={
            "current_password": "x", "new_password": "y",
        })
        assert resp.status_code == 401


# --- Delete account ---

class TestDeleteAccount:
    async def test_delete_account(self, client: AsyncClient, db: AsyncSession):
        token = await register_and_login(client, db)
        resp = await client.post(
            "/api/profile/deactivate",
            json={"password": "ValidPass1"},
            headers=auth(token),
        )
        assert resp.status_code == 204

        # Should no longer be able to login
        resp = await client.post("/api/auth/login", json={
            "email": "user@test.com",
            "password": "ValidPass1",
        })
        assert resp.status_code == 401

    async def test_delete_account_wrong_password(self, client: AsyncClient, db: AsyncSession):
        token = await register_and_login(client, db)
        resp = await client.post(
            "/api/profile/deactivate",
            json={"password": "WrongPass1"},
            headers=auth(token),
        )
        assert resp.status_code == 401

    async def test_delete_account_unauthenticated(self, client: AsyncClient):
        resp = await client.post("/api/profile/deactivate", json={"password": "x"})
        assert resp.status_code == 401
