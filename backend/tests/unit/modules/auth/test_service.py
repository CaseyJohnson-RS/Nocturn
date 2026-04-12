"""Unit tests for AuthService."""

import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from argon2 import PasswordHasher

from src.app.common.exceptions import (
    ConflictError,
    NotFoundError,
    UnauthorizedError,
    ValidationError,
)
from src.app.config import settings
from src.app.modules.auth.service import AuthService, validate_password

ph = PasswordHasher()

# --- Fixtures ---


@pytest.fixture()
def repo():
    return AsyncMock()


@pytest.fixture()
def service(repo: AsyncMock):
    svc = AuthService.__new__(AuthService)
    svc.repo = repo
    return svc


@pytest.fixture()
def active_user():
    user = MagicMock()
    user.id = uuid.uuid4()
    user.email = "user@example.com"
    user.nickname = "testuser"
    user.role = "user"
    user.is_email_confirmed = True
    user.is_active = True
    user.password_hash = ph.hash("Valid1pass")
    return user


@pytest.fixture()
def unconfirmed_user(active_user: MagicMock):
    active_user.is_email_confirmed = False
    return active_user


@pytest.fixture()
def blocked_user(active_user: MagicMock):
    active_user.is_active = False
    return active_user


# --- _validate_password ---


class TestValidatePassword:
    def test_valid(self):
        validate_password("Valid1pass")

    @pytest.mark.parametrize("pwd", ["alllowercase1", "ALLUPPERCASE1", "NoDigitsHere", "123456"])
    def test_invalid(self, pwd: str):
        with pytest.raises(ValidationError):
            validate_password(pwd)


# --- register ---


class TestRegister:
    @pytest.mark.anyio()
    @patch("src.app.modules.auth.service.send_confirmation_email", new_callable=AsyncMock)
    async def test_register_new_user(
        self, mock_email: AsyncMock, service: AuthService, repo: AsyncMock
    ):
        repo.get_user_by_email.return_value = None
        repo.create_user.return_value = MagicMock(id=uuid.uuid4())

        result = await service.register("new@example.com", "Valid1pass", "nick")

        repo.create_user.assert_called_once()
        repo.create_verification_token.assert_called_once()
        mock_email.assert_called_once()
        assert "confirmation" in result.lower()

    @pytest.mark.anyio()
    async def test_register_existing_user_updates(
        self, service: AuthService, repo: AsyncMock, unconfirmed_user: MagicMock,
    ) -> None:
        repo.get_user_by_email.return_value = unconfirmed_user

        with patch("src.app.modules.auth.service.send_confirmation_email", new_callable=AsyncMock):
            await service.register("user@example.com", "Valid1pass", "newnick")

        repo.update_nickname.assert_called_once_with(unconfirmed_user.id, "newnick")
        repo.update_password.assert_called_once()
        repo.create_user.assert_not_called()

    @pytest.mark.anyio()
    async def test_register_weak_password(self, service: AuthService):
        with pytest.raises(ValidationError):
            await service.register("a@b.com", "weakpass", "nick")


# --- confirm_email ---


class TestConfirmEmail:
    @pytest.mark.anyio()
    async def test_valid_token(self, service: AuthService, repo: AsyncMock):
        vt = MagicMock()
        vt.user_id = uuid.uuid4()
        vt.expires_at = datetime.now(UTC) + timedelta(hours=1)
        repo.get_verification_token_by_hash.return_value = vt

        await service.confirm_email("raw-token")

        repo.confirm_email.assert_called_once_with(vt.user_id)
        repo.delete_verification_token.assert_called_once_with(vt.id)

    @pytest.mark.anyio()
    async def test_expired_token(self, service: AuthService, repo: AsyncMock):
        vt = MagicMock()
        vt.expires_at = datetime.now(UTC) - timedelta(hours=1)
        repo.get_verification_token_by_hash.return_value = vt

        with pytest.raises(NotFoundError):
            await service.confirm_email("raw-token")

    @pytest.mark.anyio()
    async def test_invalid_token(self, service: AuthService, repo: AsyncMock):
        repo.get_verification_token_by_hash.return_value = None

        with pytest.raises(NotFoundError):
            await service.confirm_email("bogus")


# --- login ---


class TestLogin:
    @pytest.mark.anyio()
    async def test_success(self, service: AuthService, repo: AsyncMock, active_user: MagicMock):
        repo.get_user_by_email.return_value = active_user
        repo.count_user_sessions.return_value = 0

        token_resp, refresh_raw = await service.login("user@example.com", "Valid1pass")

        assert token_resp.access_token
        assert refresh_raw
        repo.create_refresh_token.assert_called_once()

    @pytest.mark.anyio()
    async def test_wrong_password(
        self, service: AuthService, repo: AsyncMock, active_user: MagicMock
    ):
        repo.get_user_by_email.return_value = active_user

        with pytest.raises(UnauthorizedError, match="Invalid credentials"):
            await service.login("user@example.com", "WrongPass1")

    @pytest.mark.anyio()
    async def test_user_not_found(self, service: AuthService, repo: AsyncMock):
        repo.get_user_by_email.return_value = None

        with pytest.raises(UnauthorizedError, match="Invalid credentials"):
            await service.login("no@example.com", "Valid1pass")

    @pytest.mark.anyio()
    async def test_email_not_confirmed(
        self, service: AuthService, repo: AsyncMock, unconfirmed_user: MagicMock
    ):
        repo.get_user_by_email.return_value = unconfirmed_user

        with pytest.raises(UnauthorizedError, match="Email not confirmed"):
            await service.login("user@example.com", "Valid1pass")

    @pytest.mark.anyio()
    async def test_blocked_user(
        self, service: AuthService, repo: AsyncMock, blocked_user: MagicMock
    ):
        repo.get_user_by_email.return_value = blocked_user

        with pytest.raises(UnauthorizedError, match="blocked"):
            await service.login("user@example.com", "Valid1pass")

    @pytest.mark.anyio()
    async def test_session_limit(
        self, service: AuthService, repo: AsyncMock, active_user: MagicMock
    ):
        repo.get_user_by_email.return_value = active_user
        repo.count_user_sessions.return_value = settings.max_sessions_per_user

        with pytest.raises(ConflictError, match="sessions"):
            await service.login("user@example.com", "Valid1pass")


# --- refresh ---


class TestRefresh:
    @pytest.mark.anyio()
    async def test_success_rotates_token(
        self, service: AuthService, repo: AsyncMock, active_user: MagicMock
    ):
        rt = MagicMock()
        rt.user_id = active_user.id
        rt.expires_at = datetime.now(UTC) + timedelta(days=1)
        repo.get_refresh_token_by_hash.return_value = rt
        repo.get_user_by_id.return_value = active_user

        token_resp, new_refresh = await service.refresh("old-refresh-token")

        repo.delete_refresh_token.assert_called_once_with(rt.id)
        repo.create_refresh_token.assert_called_once()
        assert token_resp.access_token
        assert new_refresh

    @pytest.mark.anyio()
    async def test_invalid_token(self, service: AuthService, repo: AsyncMock):
        repo.get_refresh_token_by_hash.return_value = None

        with pytest.raises(UnauthorizedError, match="Invalid refresh"):
            await service.refresh("bogus")

    @pytest.mark.anyio()
    async def test_expired_token(self, service: AuthService, repo: AsyncMock):
        rt = MagicMock()
        rt.expires_at = datetime.now(UTC) - timedelta(days=1)
        repo.get_refresh_token_by_hash.return_value = rt

        with pytest.raises(UnauthorizedError, match="expired"):
            await service.refresh("expired-token")

        repo.delete_refresh_token.assert_called_once()

    @pytest.mark.anyio()
    async def test_inactive_user(
        self, service: AuthService, repo: AsyncMock, blocked_user: MagicMock
    ):
        rt = MagicMock()
        rt.user_id = blocked_user.id
        rt.expires_at = datetime.now(UTC) + timedelta(days=1)
        repo.get_refresh_token_by_hash.return_value = rt
        repo.get_user_by_id.return_value = blocked_user

        with pytest.raises(UnauthorizedError, match="unavailable"):
            await service.refresh("some-token")


# --- logout ---


class TestLogout:
    @pytest.mark.anyio()
    async def test_valid_token(self, service: AuthService, repo: AsyncMock):
        rt = MagicMock()
        repo.get_refresh_token_by_hash.return_value = rt

        await service.logout("some-token")

        repo.delete_refresh_token.assert_called_once_with(rt.id)

    @pytest.mark.anyio()
    async def test_unknown_token_is_noop(self, service: AuthService, repo: AsyncMock):
        repo.get_refresh_token_by_hash.return_value = None

        await service.logout("bogus")

        repo.delete_refresh_token.assert_not_called()


# --- request_password_reset ---


class TestRequestPasswordReset:
    @pytest.mark.anyio()
    @patch("src.app.modules.auth.service.send_password_reset_email", new_callable=AsyncMock)
    async def test_confirmed_user_sends_email(
        self, mock_email: AsyncMock, service: AuthService, repo: AsyncMock, active_user: MagicMock
    ):
        repo.get_user_by_email.return_value = active_user

        result = await service.request_password_reset("user@example.com")

        mock_email.assert_called_once()
        repo.create_verification_token.assert_called_once()
        assert "reset" in result.lower()

    @pytest.mark.anyio()
    @patch("src.app.modules.auth.service.send_password_reset_email", new_callable=AsyncMock)
    async def test_unknown_email_no_leak(
        self, mock_email: AsyncMock, service: AuthService, repo: AsyncMock
    ):
        repo.get_user_by_email.return_value = None

        result = await service.request_password_reset("unknown@example.com")

        mock_email.assert_not_called()
        assert "reset" in result.lower()


# --- reset_password ---


class TestResetPassword:
    @pytest.mark.anyio()
    async def test_success(self, service: AuthService, repo: AsyncMock):
        vt = MagicMock()
        vt.user_id = uuid.uuid4()
        vt.expires_at = datetime.now(UTC) + timedelta(hours=1)
        repo.get_verification_token_by_hash.return_value = vt

        await service.reset_password("raw-token", "NewValid1")

        repo.update_password.assert_called_once()
        repo.delete_verification_token.assert_called_once()
        repo.delete_all_user_refresh_tokens.assert_called_once_with(vt.user_id)

    @pytest.mark.anyio()
    async def test_expired_token(self, service: AuthService, repo: AsyncMock):
        vt = MagicMock()
        vt.expires_at = datetime.now(UTC) - timedelta(hours=1)
        repo.get_verification_token_by_hash.return_value = vt

        with pytest.raises(NotFoundError):
            await service.reset_password("raw-token", "NewValid1")

    @pytest.mark.anyio()
    async def test_weak_password(self, service: AuthService):
        with pytest.raises(ValidationError):
            await service.reset_password("raw-token", "weak")


# --- resend_confirmation ---


class TestResendConfirmation:
    @pytest.mark.anyio()
    @patch("src.app.modules.auth.service.send_confirmation_email", new_callable=AsyncMock)
    async def test_unconfirmed_user_sends(
        self,
        mock_email: AsyncMock,
        service: AuthService,
        repo: AsyncMock,
        unconfirmed_user: MagicMock,
    ):
        repo.get_user_by_email.return_value = unconfirmed_user

        await service.resend_confirmation("user@example.com")

        mock_email.assert_called_once()

    @pytest.mark.anyio()
    @patch("src.app.modules.auth.service.send_confirmation_email", new_callable=AsyncMock)
    async def test_confirmed_user_no_send(
        self, mock_email: AsyncMock, service: AuthService, repo: AsyncMock, active_user: MagicMock
    ):
        repo.get_user_by_email.return_value = active_user

        await service.resend_confirmation("user@example.com")

        mock_email.assert_not_called()


# --- get_user ---


class TestGetUser:
    @pytest.mark.anyio()
    async def test_found(self, service: AuthService, repo: AsyncMock, active_user: MagicMock):
        repo.get_user_by_id.return_value = active_user

        result = await service.get_user(active_user.id)

        assert result == active_user

    @pytest.mark.anyio()
    async def test_not_found(self, service: AuthService, repo: AsyncMock):
        repo.get_user_by_id.return_value = None

        with pytest.raises(NotFoundError):
            await service.get_user(uuid.uuid4())


# --- JWT ---


class TestJWT:
    def test_roundtrip(self):
        user_id = uuid.uuid4()
        token = AuthService.create_access_token(user_id, "user")
        payload = AuthService.decode_access_token(token)

        assert payload["sub"] == str(user_id)
        assert payload["role"] == "user"

    def test_expired_token(self):
        user_id = uuid.uuid4()
        with patch("src.app.modules.auth.service.settings") as mock_settings:
            mock_settings.jwt_secret = settings.jwt_secret
            mock_settings.access_token_ttl_minutes = -1
            token = AuthService.create_access_token(user_id, "user")

        with pytest.raises(UnauthorizedError, match="expired"):
            AuthService.decode_access_token(token)

    def test_invalid_token(self):
        with pytest.raises(UnauthorizedError, match="Invalid"):
            AuthService.decode_access_token("garbage.token.here")
