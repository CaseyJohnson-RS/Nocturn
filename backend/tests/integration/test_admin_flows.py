"""Integration tests for admin flows."""

from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.auth.models import User

REGISTER = "/api/auth/register"
LOGIN = "/api/auth/login"
USERS = "/api/admin/users"

ADMIN_USER = {"email": "admin@example.com", "password": "Admin1pass", "nickname": "admin"}
REGULAR_USER = {"email": "user@example.com", "password": "Valid1pass", "nickname": "testuser"}


# --- Helpers ---


async def _create_and_login(
    client: AsyncClient,
    db: AsyncSession,
    user_data: dict[str, str],
    role: str = "user",
) -> str:
    with patch("app.modules.auth.service.send_confirmation_email", new_callable=AsyncMock):
        await client.post(REGISTER, json=user_data)

    result = await db.execute(select(User).where(User.email == user_data["email"]))
    user: User = result.scalar_one()
    user.is_email_confirmed = True
    user.role = role
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


# --- List users ---


class TestListUsers:
    @pytest.mark.anyio()
    async def test_returns_all_users(self, client: AsyncClient, db: AsyncSession) -> None:
        admin_token = await _create_and_login(client, db, ADMIN_USER, role="admin")
        await _create_and_login(client, db, REGULAR_USER)

        resp = await client.get(USERS, headers=_auth(admin_token))

        assert resp.status_code == 200
        assert resp.json()["total"] == 2
        assert len(resp.json()["items"]) == 2

    @pytest.mark.anyio()
    async def test_search_filters(self, client: AsyncClient, db: AsyncSession) -> None:
        admin_token = await _create_and_login(client, db, ADMIN_USER, role="admin")
        await _create_and_login(client, db, REGULAR_USER)

        resp = await client.get(USERS, params={"search": "testuser"}, headers=_auth(admin_token))

        assert resp.status_code == 200
        assert resp.json()["total"] == 1
        assert resp.json()["items"][0]["nickname"] == "testuser"

    @pytest.mark.anyio()
    async def test_pagination(self, client: AsyncClient, db: AsyncSession) -> None:
        admin_token = await _create_and_login(client, db, ADMIN_USER, role="admin")
        await _create_and_login(client, db, REGULAR_USER)

        resp = await client.get(USERS, params={"limit": 1, "offset": 0}, headers=_auth(admin_token))

        assert resp.status_code == 200
        assert len(resp.json()["items"]) == 1
        assert resp.json()["total"] == 2

    @pytest.mark.anyio()
    async def test_forbidden_for_regular_user(self, client: AsyncClient, db: AsyncSession) -> None:
        user_token = await _create_and_login(client, db, REGULAR_USER)

        resp = await client.get(USERS, headers=_auth(user_token))

        assert resp.status_code == 403


# --- Get user ---


class TestGetUser:
    @pytest.mark.anyio()
    async def test_success(self, client: AsyncClient, db: AsyncSession) -> None:
        admin_token = await _create_and_login(client, db, ADMIN_USER, role="admin")
        await _create_and_login(client, db, REGULAR_USER)

        result = await db.execute(select(User).where(User.email == REGULAR_USER["email"]))
        user: User = result.scalar_one()

        resp = await client.get(f"{USERS}/{user.id}", headers=_auth(admin_token))

        assert resp.status_code == 200
        assert resp.json()["email"] == REGULAR_USER["email"]

    @pytest.mark.anyio()
    async def test_not_found(self, client: AsyncClient, db: AsyncSession) -> None:
        admin_token = await _create_and_login(client, db, ADMIN_USER, role="admin")

        import uuid

        resp = await client.get(f"{USERS}/{uuid.uuid4()}", headers=_auth(admin_token))

        assert resp.status_code == 404


# --- Set active ---


class TestSetActive:
    @pytest.mark.anyio()
    async def test_deactivate_user(self, client: AsyncClient, db: AsyncSession) -> None:
        admin_token = await _create_and_login(client, db, ADMIN_USER, role="admin")
        await _create_and_login(client, db, REGULAR_USER)

        result = await db.execute(select(User).where(User.email == REGULAR_USER["email"]))
        user: User = result.scalar_one()

        resp = await client.put(
            f"{USERS}/{user.id}/active",
            json={"is_active": False},
            headers=_auth(admin_token),
        )

        assert resp.status_code == 200
        assert resp.json()["is_active"] is False

        # Deactivated user cannot login
        resp = await client.post(
            LOGIN,
            json={
                "email": REGULAR_USER["email"],
                "password": REGULAR_USER["password"],
            },
        )
        assert resp.status_code == 401

    @pytest.mark.anyio()
    async def test_reactivate_user(self, client: AsyncClient, db: AsyncSession) -> None:
        admin_token = await _create_and_login(client, db, ADMIN_USER, role="admin")
        await _create_and_login(client, db, REGULAR_USER)

        result = await db.execute(select(User).where(User.email == REGULAR_USER["email"]))
        user: User = result.scalar_one()

        await client.put(
            f"{USERS}/{user.id}/active",
            json={"is_active": False},
            headers=_auth(admin_token),
        )
        resp = await client.put(
            f"{USERS}/{user.id}/active",
            json={"is_active": True},
            headers=_auth(admin_token),
        )

        assert resp.status_code == 200
        assert resp.json()["is_active"] is True

        # Reactivated user can login
        resp = await client.post(
            LOGIN,
            json={
                "email": REGULAR_USER["email"],
                "password": REGULAR_USER["password"],
            },
        )
        assert resp.status_code == 200

    @pytest.mark.anyio()
    async def test_cannot_deactivate_self(self, client: AsyncClient, db: AsyncSession) -> None:
        admin_token = await _create_and_login(client, db, ADMIN_USER, role="admin")

        result = await db.execute(select(User).where(User.email == ADMIN_USER["email"]))
        admin: User = result.scalar_one()

        resp = await client.put(
            f"{USERS}/{admin.id}/active",
            json={"is_active": False},
            headers=_auth(admin_token),
        )

        assert resp.status_code == 403


# --- Set role ---


class TestSetRole:
    @pytest.mark.anyio()
    async def test_promote_to_admin(self, client: AsyncClient, db: AsyncSession) -> None:
        admin_token = await _create_and_login(client, db, ADMIN_USER, role="admin")
        await _create_and_login(client, db, REGULAR_USER)

        result = await db.execute(select(User).where(User.email == REGULAR_USER["email"]))
        user: User = result.scalar_one()

        resp = await client.put(
            f"{USERS}/{user.id}/role",
            json={"role": "admin"},
            headers=_auth(admin_token),
        )

        assert resp.status_code == 200
        assert resp.json()["role"] == "admin"

    @pytest.mark.anyio()
    async def test_demote_to_user(self, client: AsyncClient, db: AsyncSession) -> None:
        admin_token = await _create_and_login(client, db, ADMIN_USER, role="admin")

        second_admin = {
            "email": "admin2@example.com",
            "password": "Admin1pass",
            "nickname": "admin2",
        }
        await _create_and_login(client, db, second_admin, role="admin")

        result = await db.execute(select(User).where(User.email == second_admin["email"]))
        user: User = result.scalar_one()

        resp = await client.put(
            f"{USERS}/{user.id}/role",
            json={"role": "user"},
            headers=_auth(admin_token),
        )

        assert resp.status_code == 200
        assert resp.json()["role"] == "user"

    @pytest.mark.anyio()
    async def test_cannot_change_own_role(self, client: AsyncClient, db: AsyncSession) -> None:
        admin_token = await _create_and_login(client, db, ADMIN_USER, role="admin")

        result = await db.execute(select(User).where(User.email == ADMIN_USER["email"]))
        admin: User = result.scalar_one()

        resp = await client.put(
            f"{USERS}/{admin.id}/role",
            json={"role": "user"},
            headers=_auth(admin_token),
        )

        assert resp.status_code == 403
