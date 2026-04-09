"""Integration tests for auth flows."""

from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.auth.models import User, VerificationToken

PREFIX = "/api/auth/"

REGISTER = PREFIX + "register"
LOGIN = PREFIX + "login"
REFRESH = PREFIX + "refresh"
LOGOUT = PREFIX + "logout"
CONFIRM = "confirm-email"
REQUEST_RESET = PREFIX + "request-password-reset"
RESET = PREFIX + "reset-password"
RESEND = PREFIX + "resend-confirmation"
ME = PREFIX + "me"

VALID_USER = {"email": "user@example.com", "password": "Valid1pass", "nickname": "testuser"}
COOKIE = "refresh_token"


# --- Helpers ---


async def _get_verification_token(db: AsyncSession, token_type: str) -> VerificationToken | None:
    result = await db.execute(select(VerificationToken).where(VerificationToken.type == token_type))
    return result.scalar_one_or_none()


async def _register_and_confirm(client: AsyncClient, db: AsyncSession) -> None:
    """Register a user and confirm their email."""
    with patch("app.modules.auth.service.send_confirmation_email", new_callable=AsyncMock):
        await client.post(REGISTER, json=VALID_USER)

    vt = await _get_verification_token(db, "email_confirm")
    assert vt is not None

    # We need the raw token, but DB has the hash.
    # Shortcut: confirm directly via DB.
    await db.execute(select(User).where(User.email == VALID_USER["email"]))
    user = (await db.execute(select(User).where(User.email == VALID_USER["email"]))).scalar_one()
    user.is_email_confirmed = True
    await db.commit()


async def _login(client: AsyncClient) -> tuple[str, str]:
    """Login and return (access_token, refresh_cookie)."""
    resp = await client.post(
        LOGIN,
        json={
            "email": VALID_USER["email"],
            "password": VALID_USER["password"],
        },
    )
    assert resp.status_code == 200
    access = resp.json()["access_token"]
    refresh = resp.cookies.get(COOKIE)
    assert refresh
    return access, refresh


# --- Registration flow ---


class TestRegistrationFlow:
    @pytest.mark.anyio()
    async def test_register_sends_confirmation(self, client: AsyncClient, db: AsyncSession) -> None:
        with patch(
            "app.modules.auth.service.send_confirmation_email", new_callable=AsyncMock
        ) as mock_email:
            resp = await client.post(REGISTER, json=VALID_USER)

        assert resp.status_code == 200
        mock_email.assert_called_once()

        user = (
            await db.execute(select(User).where(User.email == VALID_USER["email"]))
        ).scalar_one()
        assert not user.is_email_confirmed

        vt = await _get_verification_token(db, "email_confirm")
        assert vt is not None
        assert vt.user_id == user.id

    @pytest.mark.anyio()
    async def test_cannot_login_before_confirmation(self, client: AsyncClient) -> None:
        with patch("app.modules.auth.service.send_confirmation_email", new_callable=AsyncMock):
            await client.post(REGISTER, json=VALID_USER)

        resp = await client.post(
            LOGIN,
            json={
                "email": VALID_USER["email"],
                "password": VALID_USER["password"],
            },
        )
        assert resp.status_code == 401


# --- Full auth flow ---


class TestFullAuthFlow:
    @pytest.mark.anyio()
    async def test_register_confirm_login_refresh_logout(
        self,
        client: AsyncClient,
        db: AsyncSession,
    ) -> None:
        # 1. Register + confirm
        await _register_and_confirm(client, db)

        # 2. Login
        access, refresh = await _login(client)

        # 3. Access /me
        resp = await client.get(ME, headers={"Authorization": f"Bearer {access}"})
        assert resp.status_code == 200
        assert resp.json()["email"] == VALID_USER["email"]
        assert resp.json()["nickname"] == VALID_USER["nickname"]

        # 4. Refresh
        resp = await client.post(REFRESH, cookies={COOKIE: refresh})
        assert resp.status_code == 200
        new_refresh = resp.cookies.get(COOKIE)

        # 5. Old refresh token is revoked
        resp = await client.post(REFRESH, cookies={COOKIE: refresh})
        assert resp.status_code == 401

        # 6. Logout
        assert new_refresh is not None
        resp = await client.post(LOGOUT, cookies={COOKIE: new_refresh})
        assert resp.status_code == 200

        # 7. Refresh after logout fails
        resp = await client.post(REFRESH, cookies={COOKIE: new_refresh})
        assert resp.status_code == 401


# --- /me ---


class TestMe:
    @pytest.mark.anyio()
    async def test_unauthorized_without_token(self, client: AsyncClient) -> None:
        resp = await client.get(ME)
        assert resp.status_code == 401

    @pytest.mark.anyio()
    async def test_invalid_token(self, client: AsyncClient) -> None:
        resp = await client.get(ME, headers={"Authorization": "Bearer garbage"})
        assert resp.status_code == 401


# --- Password reset flow ---


class TestPasswordResetFlow:
    @pytest.mark.anyio()
    async def test_reset_and_login_with_new_password(
        self,
        client: AsyncClient,
        db: AsyncSession,
    ) -> None:
        await _register_and_confirm(client, db)

        # Request reset
        with patch(
            "app.modules.auth.service.send_password_reset_email", new_callable=AsyncMock
        ) as mock_email:
            resp = await client.post(REQUEST_RESET, json={"email": VALID_USER["email"]})

        assert resp.status_code == 200
        mock_email.assert_called_once()

        # Get raw token — we can't recover it from hash,
        # so grab it from the mock call args
        raw_token = mock_email.call_args[0][1]

        # Reset password
        new_password = "NewValid1pass"
        resp = await client.post(RESET, json={"token": raw_token, "new_password": new_password})
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
    async def test_reset_revokes_all_sessions(
        self,
        client: AsyncClient,
        db: AsyncSession,
    ) -> None:
        await _register_and_confirm(client, db)
        _, refresh = await _login(client)

        with patch(
            "app.modules.auth.service.send_password_reset_email", new_callable=AsyncMock
        ) as mock_email:
            await client.post(REQUEST_RESET, json={"email": VALID_USER["email"]})

        raw_token = mock_email.call_args[0][1]
        await client.post(RESET, json={"token": raw_token, "new_password": "NewValid1pass"})

        # Old refresh token is dead
        resp = await client.post(REFRESH, cookies={COOKIE: refresh})
        assert resp.status_code == 401


# --- Session limit ---


class TestSessionLimit:
    @pytest.mark.anyio()
    async def test_max_sessions_exceeded(self, client: AsyncClient, db: AsyncSession) -> None:
        await _register_and_confirm(client, db)

        for _ in range(5):  # max_sessions_per_user default = 5
            resp = await client.post(
                LOGIN,
                json={
                    "email": VALID_USER["email"],
                    "password": VALID_USER["password"],
                },
            )
            assert resp.status_code == 200

        # 6th login should fail
        resp = await client.post(
            LOGIN,
            json={
                "email": VALID_USER["email"],
                "password": VALID_USER["password"],
            },
        )
        assert resp.status_code == 409


# --- Anti-enumeration ---


class TestAntiEnumeration:
    @pytest.mark.anyio()
    async def test_reset_unknown_email_same_response(self, client: AsyncClient) -> None:
        resp = await client.post(REQUEST_RESET, json={"email": "unknown@example.com"})
        assert resp.status_code == 200
        assert "reset" in resp.json()["message"].lower()

    @pytest.mark.anyio()
    async def test_resend_unknown_email_same_response(self, client: AsyncClient) -> None:
        resp = await client.post(RESEND, json={"email": "unknown@example.com"})
        assert resp.status_code == 200
        assert "confirmation" in resp.json()["message"].lower()
