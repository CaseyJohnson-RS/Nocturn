"""Integration tests for profile flows."""

from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

REGISTER = "/api/auth/register"
LOGIN = "/api/auth/login"
NICKNAME = "/api/profile/nickname"
PASSWORD = "/api/profile/password"
DELETE = "/api/profile/delete_account"
ME = "/api/auth/me"

VALID_USER = {"email": "user@example.com", "password": "Valid1pass", "nickname": "testuser"}


# --- Helpers ---


async def _register_confirm_login(client: AsyncClient, db: AsyncGenerator[AsyncSession]) -> str:
    """Register, confirm via DB, login. Returns access token."""
    with patch("src.app.modules.auth.service.send_confirmation_email", new_callable=AsyncMock):
        await client.post(REGISTER, json=VALID_USER)

    from sqlalchemy import select

    from src.app.modules.auth.models import User

    user = (await db.execute(select(User).where(User.email == VALID_USER["email"]))).scalar_one()  # type: ignore
    user.is_email_confirmed = True
    await db.commit()  # type: ignore

    resp = await client.post(
        LOGIN,
        json={
            "email": VALID_USER["email"],
            "password": VALID_USER["password"],
        },
    )
    return resp.json()["access_token"]


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


# --- Nickname ---


class TestNicknameFlow:
    @pytest.mark.anyio()
    async def test_update_nickname(
        self, client: AsyncClient, db: AsyncGenerator[AsyncSession]
    ) -> None:
        token = await _register_confirm_login(client, db)

        resp = await client.put(NICKNAME, json={"nickname": "newnick"}, headers=_auth(token))

        assert resp.status_code == 200
        assert resp.json()["nickname"] == "newnick"

        # Verify via /me
        resp = await client.get(ME, headers=_auth(token))
        assert resp.json()["nickname"] == "newnick"

    @pytest.mark.anyio()
    async def test_same_nickname_is_noop(
        self, client: AsyncClient, db: AsyncGenerator[AsyncSession]
    ) -> None:
        token = await _register_confirm_login(client, db)

        resp = await client.put(
            NICKNAME,
            json={"nickname": VALID_USER["nickname"]},
            headers=_auth(token),
        )

        assert resp.status_code == 200
        assert resp.json()["nickname"] == VALID_USER["nickname"]

    @pytest.mark.anyio()
    async def test_nickname_taken_by_another_user(
        self, client: AsyncClient, db: AsyncGenerator[AsyncSession]
    ) -> None:
        token = await _register_confirm_login(client, db)

        # Register second user
        second = {"email": "other@example.com", "password": "Valid1pass", "nickname": "taken"}
        with patch("src.app.modules.auth.service.send_confirmation_email", new_callable=AsyncMock):
            await client.post(REGISTER, json=second)

        from sqlalchemy import select

        from src.app.modules.auth.models import User

        user2 = (await db.execute(select(User).where(User.email == second["email"]))).scalar_one()  # type: ignore
        user2.is_email_confirmed = True
        await db.commit()  # type: ignore

        resp = await client.put(NICKNAME, json={"nickname": "taken"}, headers=_auth(token))

        assert resp.status_code == 409

    @pytest.mark.anyio()
    async def test_unauthorized(self, client: AsyncClient) -> None:
        resp = await client.put(NICKNAME, json={"nickname": "newnick"})

        assert resp.status_code == 401


# --- Password ---


class TestPasswordFlow:
    @pytest.mark.anyio()
    async def test_change_password_and_login(
        self, client: AsyncClient, db: AsyncGenerator[AsyncSession]
    ) -> None:
        token = await _register_confirm_login(client, db)
        new_password = "NewValid1pass"

        resp = await client.put(
            PASSWORD,
            json={
                "current_password": VALID_USER["password"],
                "new_password": new_password,
            },
            headers=_auth(token),
        )

        assert resp.status_code == 200

        # Old password fails
        resp = await client.post(
            LOGIN,
            json={
                "email": VALID_USER["email"],
                "password": VALID_USER["password"],
            },
        )
        assert resp.status_code == 401

        # New password works
        resp = await client.post(
            LOGIN,
            json={
                "email": VALID_USER["email"],
                "password": new_password,
            },
        )
        assert resp.status_code == 200

    @pytest.mark.anyio()
    async def test_wrong_current_password(
        self, client: AsyncClient, db: AsyncGenerator[AsyncSession]
    ) -> None:
        token = await _register_confirm_login(client, db)

        resp = await client.put(
            PASSWORD,
            json={
                "current_password": "Wrong1pass",
                "new_password": "NewValid1pass",
            },
            headers=_auth(token),
        )

        assert resp.status_code == 401

    @pytest.mark.anyio()
    async def test_weak_new_password(
        self, client: AsyncClient, db: AsyncGenerator[AsyncSession]
    ) -> None:
        token = await _register_confirm_login(client, db)

        resp = await client.put(
            PASSWORD,
            json={
                "current_password": VALID_USER["password"],
                "new_password": "alllowercase1",
            },
            headers=_auth(token),
        )

        assert resp.status_code == 400


# --- Delete account ---


class TestDeleteAccountFlow:
    @pytest.mark.anyio()
    async def test_deactivate_and_cannot_login(
        self, client: AsyncClient, db: AsyncGenerator[AsyncSession]
    ) -> None:
        token = await _register_confirm_login(client, db)

        resp = await client.post(
            DELETE,
            json={
                "password": VALID_USER["password"],
            },
            headers=_auth(token),
        )

        assert resp.status_code == 204

        # Login fails after deactivation
        resp = await client.post(
            LOGIN,
            json={
                "email": VALID_USER["email"],
                "password": VALID_USER["password"],
            },
        )
        assert resp.status_code == 401

    @pytest.mark.anyio()
    async def test_wrong_password(
        self, client: AsyncClient, db: AsyncGenerator[AsyncSession]
    ) -> None:
        token = await _register_confirm_login(client, db)

        resp = await client.post(
            DELETE,
            json={
                "password": "Wrong1pass",
            },
            headers=_auth(token),
        )

        assert resp.status_code == 401

        # Account still works
        resp = await client.get(ME, headers=_auth(token))
        assert resp.status_code == 200
