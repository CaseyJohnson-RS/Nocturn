import hashlib
import secrets
import uuid
from datetime import UTC, datetime, timedelta

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.common.email import send_confirmation_email, send_password_reset_email
from app.common.exceptions import ConflictError, NotFoundError, UnauthorizedError, ValidationError
from app.modules.auth.repository import AuthRepository
from app.modules.auth.schemas import TokenResponse

ph = PasswordHasher()


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _validate_password(password: str) -> None:
    has_upper = any(c.isupper() for c in password)
    has_lower = any(c.islower() for c in password)
    has_digit = any(c.isdigit() for c in password)
    if not (has_upper and has_lower and has_digit):
        raise ValidationError("Password must contain at least one uppercase letter, one lowercase letter, and one digit")


class AuthService:
    def __init__(self, db: AsyncSession):
        self.repo = AuthRepository(db)

    # --- JWT ---

    @staticmethod
    def create_access_token(user_id: uuid.UUID, role: str) -> str:
        now = datetime.now(UTC)
        payload = {
            "sub": str(user_id),
            "role": role,
            "iat": now,
            "exp": now + timedelta(minutes=settings.access_token_ttl_minutes),
        }
        return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")

    @staticmethod
    def decode_access_token(token: str) -> dict:
        try:
            return jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
        except jwt.ExpiredSignatureError:
            raise UnauthorizedError("Token expired")
        except jwt.InvalidTokenError:
            raise UnauthorizedError("Invalid token")

    # --- Registration ---

    async def register(self, email: str, password: str, nickname: str) -> str:
        _validate_password(password)

        existing = await self.repo.get_user_by_email(email)
        if existing:
            # Anti-enumeration: return same response
            return "If this email is not registered, a confirmation link has been sent"

        existing_nick = await self.repo.get_user_by_nickname(nickname)
        if existing_nick:
            raise ConflictError("Nickname already taken")

        password_hash = ph.hash(password)
        user = await self.repo.create_user(email, nickname, password_hash)

        # Create email confirmation token
        raw_token = secrets.token_urlsafe(32)
        token_hash = _hash_token(raw_token)
        expires_at = datetime.now(UTC) + timedelta(hours=settings.email_confirm_ttl_hours)
        await self.repo.create_verification_token(user.id, "email_confirm", token_hash, expires_at)

        await send_confirmation_email(email, raw_token)

        return "If this email is not registered, a confirmation link has been sent"

    # --- Email confirmation ---

    async def confirm_email(self, raw_token: str) -> None:
        token_hash = _hash_token(raw_token)
        vt = await self.repo.get_verification_token_by_hash(token_hash, "email_confirm")
        if not vt or vt.expires_at < datetime.now(UTC):
            raise NotFoundError("Invalid or expired confirmation link")

        await self.repo.confirm_email(vt.user_id)
        await self.repo.delete_verification_token(vt.id)

    # --- Login ---

    async def login(self, email: str, password: str) -> tuple[TokenResponse, str]:
        user = await self.repo.get_user_by_email(email)
        if not user:
            raise UnauthorizedError("Invalid credentials")

        try:
            ph.verify(user.password_hash, password)
        except VerifyMismatchError:
            raise UnauthorizedError("Invalid credentials")

        if not user.is_email_confirmed:
            raise UnauthorizedError("Email not confirmed")

        if not user.is_active:
            raise UnauthorizedError("Account is blocked")

        # Check session limit
        session_count = await self.repo.count_user_sessions(user.id)
        if session_count >= settings.max_sessions_per_user:
            raise ConflictError("Maximum number of active sessions reached")

        # Create tokens
        access_token = self.create_access_token(user.id, user.role)
        refresh_raw = secrets.token_urlsafe(32)
        refresh_hash = _hash_token(refresh_raw)
        expires_at = datetime.now(UTC) + timedelta(days=settings.refresh_token_ttl_days)
        await self.repo.create_refresh_token(user.id, refresh_hash, expires_at)

        # Rehash password if needed
        if ph.check_needs_rehash(user.password_hash):
            await self.repo.update_password(user.id, ph.hash(password))

        return TokenResponse(access_token=access_token), refresh_raw

    # --- Refresh ---

    async def refresh(self, raw_refresh_token: str) -> tuple[TokenResponse, str]:
        token_hash = _hash_token(raw_refresh_token)
        rt = await self.repo.get_refresh_token_by_hash(token_hash)

        if not rt:
            # Possible replay attack — revoke all sessions for safety
            # We can't determine user_id here, so just reject
            raise UnauthorizedError("Invalid refresh token")

        if rt.expires_at < datetime.now(UTC):
            await self.repo.delete_refresh_token(rt.id)
            raise UnauthorizedError("Refresh token expired")

        user = await self.repo.get_user_by_id(rt.user_id)
        if not user or not user.is_active:
            await self.repo.delete_refresh_token(rt.id)
            raise UnauthorizedError("Account unavailable")

        # Rotate: delete old, create new
        await self.repo.delete_refresh_token(rt.id)
        new_refresh_raw = secrets.token_urlsafe(32)
        new_refresh_hash = _hash_token(new_refresh_raw)
        expires_at = datetime.now(UTC) + timedelta(days=settings.refresh_token_ttl_days)
        await self.repo.create_refresh_token(user.id, new_refresh_hash, expires_at)

        access_token = self.create_access_token(user.id, user.role)
        return TokenResponse(access_token=access_token), new_refresh_raw

    # --- Logout ---

    async def logout(self, raw_refresh_token: str) -> None:
        token_hash = _hash_token(raw_refresh_token)
        rt = await self.repo.get_refresh_token_by_hash(token_hash)
        if rt:
            await self.repo.delete_refresh_token(rt.id)

    # --- Password reset ---

    async def request_password_reset(self, email: str) -> str:
        user = await self.repo.get_user_by_email(email)
        if user and user.is_email_confirmed:
            raw_token = secrets.token_urlsafe(32)
            token_hash = _hash_token(raw_token)
            expires_at = datetime.now(UTC) + timedelta(hours=settings.password_reset_ttl_hours)
            await self.repo.create_verification_token(user.id, "password_reset", token_hash, expires_at)
            await send_password_reset_email(user.email, raw_token)

        # Anti-enumeration
        return "If this email is registered, a password reset link has been sent"

    async def reset_password(self, raw_token: str, new_password: str) -> None:
        _validate_password(new_password)

        token_hash = _hash_token(raw_token)
        vt = await self.repo.get_verification_token_by_hash(token_hash, "password_reset")
        if not vt or vt.expires_at < datetime.now(UTC):
            raise NotFoundError("Invalid or expired reset link")

        new_hash = ph.hash(new_password)
        await self.repo.update_password(vt.user_id, new_hash)
        await self.repo.delete_verification_token(vt.id)
        # Revoke all sessions
        await self.repo.delete_all_user_refresh_tokens(vt.user_id)

    # --- Resend confirmation ---

    async def resend_confirmation(self, email: str) -> str:
        user = await self.repo.get_user_by_email(email)
        if user and not user.is_email_confirmed:
            raw_token = secrets.token_urlsafe(32)
            token_hash = _hash_token(raw_token)
            expires_at = datetime.now(UTC) + timedelta(hours=settings.email_confirm_ttl_hours)
            await self.repo.create_verification_token(user.id, "email_confirm", token_hash, expires_at)
            await send_confirmation_email(user.email, raw_token)

        # Anti-enumeration
        return "If this email is not registered, a confirmation link has been sent"
