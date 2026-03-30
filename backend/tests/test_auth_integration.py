"""Integration tests for auth endpoints — require PostgreSQL and Redis."""

import pytest
from httpx import AsyncClient
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.auth.models import User


# --- Helpers ---

async def register_user(client: AsyncClient, email="user@test.com", password="ValidPass1", nickname="testuser"):
    return await client.post("/api/auth/register", json={
        "email": email,
        "password": password,
        "nickname": nickname,
    })


async def confirm_user_email(db: AsyncSession, email: str):
    """Confirm email directly in DB."""
    await db.execute(update(User).where(User.email == email.lower()).values(is_email_confirmed=True))
    await db.commit()


async def create_confirmed_user(client: AsyncClient, db: AsyncSession, email="user@test.com", password="ValidPass1", nickname="testuser"):
    """Register and confirm a user."""
    await register_user(client, email, password, nickname)
    await confirm_user_email(db, email)
    return email, password


async def login_user(client: AsyncClient, email="user@test.com", password="ValidPass1"):
    return await client.post("/api/auth/login", json={
        "email": email,
        "password": password,
    })


# --- Registration ---

class TestRegister:
    async def test_register_success(self, client: AsyncClient):
        resp = await register_user(client)
        assert resp.status_code == 200
        assert "message" in resp.json()

    async def test_register_duplicate_email_returns_same_response(self, client: AsyncClient):
        await register_user(client)
        resp = await register_user(client, nickname="other")
        # Anti-enumeration: same 200 response
        assert resp.status_code == 200

    async def test_register_duplicate_nickname(self, client: AsyncClient):
        await register_user(client)
        resp = await register_user(client, email="other@test.com", nickname="testuser")
        assert resp.status_code == 409

    async def test_register_weak_password(self, client: AsyncClient):
        resp = await register_user(client, password="weak")
        assert resp.status_code == 422  # Pydantic validation (min_length)

    async def test_register_password_no_uppercase(self, client: AsyncClient):
        resp = await register_user(client, password="lowercase1")
        assert resp.status_code == 400

    async def test_register_invalid_nickname_chars(self, client: AsyncClient):
        resp = await register_user(client, nickname="bad name!")
        assert resp.status_code == 422

    async def test_register_nickname_too_short(self, client: AsyncClient):
        resp = await register_user(client, nickname="x")
        assert resp.status_code == 422


# --- Login ---

class TestLogin:
    async def test_login_success(self, client: AsyncClient, db: AsyncSession):
        email, password = await create_confirmed_user(client, db)
        resp = await login_user(client, email, password)
        assert resp.status_code == 200
        assert "access_token" in resp.json()
        assert "refresh_token" in resp.cookies

    async def test_login_wrong_password(self, client: AsyncClient, db: AsyncSession):
        await create_confirmed_user(client, db)
        resp = await login_user(client, password="WrongPass1")
        assert resp.status_code == 401

    async def test_login_nonexistent_email(self, client: AsyncClient):
        resp = await login_user(client, email="nobody@test.com")
        assert resp.status_code == 401

    async def test_login_unconfirmed_email(self, client: AsyncClient):
        await register_user(client)
        resp = await login_user(client)
        assert resp.status_code == 401


# --- Refresh ---

class TestRefresh:
    async def test_refresh_success(self, client: AsyncClient, db: AsyncSession):
        await create_confirmed_user(client, db)
        login_resp = await login_user(client)
        cookies = login_resp.cookies

        resp = await client.post("/api/auth/refresh", cookies={"refresh_token": cookies["refresh_token"]})
        assert resp.status_code == 200
        assert "access_token" in resp.json()

    async def test_refresh_without_cookie(self, client: AsyncClient):
        resp = await client.post("/api/auth/refresh")
        assert resp.status_code == 401

    async def test_refresh_token_rotation(self, client: AsyncClient, db: AsyncSession):
        """After refresh, old refresh token should be invalidated."""
        await create_confirmed_user(client, db)
        login_resp = await login_user(client)
        old_cookie = login_resp.cookies["refresh_token"]

        # First refresh — should succeed
        resp1 = await client.post("/api/auth/refresh", cookies={"refresh_token": old_cookie})
        assert resp1.status_code == 200

        # Second refresh with same old token — should fail (rotated)
        resp2 = await client.post("/api/auth/refresh", cookies={"refresh_token": old_cookie})
        assert resp2.status_code == 401


# --- Logout ---

class TestLogout:
    async def test_logout_success(self, client: AsyncClient, db: AsyncSession):
        await create_confirmed_user(client, db)
        login_resp = await login_user(client)
        cookies = login_resp.cookies

        resp = await client.post("/api/auth/logout", cookies={"refresh_token": cookies["refresh_token"]})
        assert resp.status_code == 200

        # Refresh should fail after logout
        resp2 = await client.post("/api/auth/refresh", cookies={"refresh_token": cookies["refresh_token"]})
        assert resp2.status_code == 401

    async def test_logout_without_cookie(self, client: AsyncClient):
        resp = await client.post("/api/auth/logout")
        assert resp.status_code == 200  # Idempotent


# --- Me ---

class TestMe:
    async def test_me_authenticated(self, client: AsyncClient, db: AsyncSession):
        await create_confirmed_user(client, db)
        login_resp = await login_user(client)
        token = login_resp.json()["access_token"]

        resp = await client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["email"] == "user@test.com"
        assert data["nickname"] == "testuser"

    async def test_me_unauthenticated(self, client: AsyncClient):
        resp = await client.get("/api/auth/me")
        assert resp.status_code == 401

    async def test_me_invalid_token(self, client: AsyncClient):
        resp = await client.get("/api/auth/me", headers={"Authorization": "Bearer invalid"})
        assert resp.status_code == 401


# --- Password Reset ---

class TestPasswordReset:
    async def test_request_reset_returns_same_for_any_email(self, client: AsyncClient):
        resp1 = await client.post("/api/auth/request-password-reset", json={"email": "exists@test.com"})
        resp2 = await client.post("/api/auth/request-password-reset", json={"email": "noone@test.com"})
        assert resp1.status_code == 200
        assert resp2.status_code == 200
        assert resp1.json() == resp2.json()


# --- Resend Confirmation ---

class TestResendConfirmation:
    async def test_resend_returns_same_for_any_email(self, client: AsyncClient):
        resp = await client.post("/api/auth/resend-confirmation", json={"email": "anyone@test.com"})
        assert resp.status_code == 200
