import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional
from passlib.context import CryptContext
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import uuid
from app.models.user import User
from app.models.email_verification_token import EmailVerificationToken
from app.schemas.auth import RegisterUserSchema, VerifyEmailRequest


pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

class AuthService:
    @staticmethod
    def hash_password(password: str) -> str:
        """Хэширует пароль с bcrypt"""
        return pwd_context.hash(password)

    @staticmethod
    def verify_password(password: str, hashed: str) -> bool:
        """Проверяет пароль"""
        return pwd_context.verify(password, hashed)

    @staticmethod
    def generate_token() -> str:
        """Генерирует случайный токен"""
        return secrets.token_urlsafe(32)

    @staticmethod
    async def register_user(db: AsyncSession, data: RegisterUserSchema) -> tuple[User, str]:
        """Регистрирует пользователя и создает токен верификации"""
        # Проверить, существует ли email
        existing = await db.execute(select(User).where(User.email == data.email))
        if existing.scalar_one_or_none():
            raise ValueError("Email already registered")

        # Создать пользователя
        user_id = uuid.uuid4()
        user = User(
            user_id=user_id,
            email=data.email,
            password_hash=AuthService.hash_password(data.password),
            username=data.username or "Unknown",
            is_email_verified=False
        )
        db.add(user)

        # Создать токен верификации (действует 24 часа)
        token = AuthService.generate_token()
        expires_at = datetime.now(timezone.utc) + timedelta(hours=24)
        verification_token = EmailVerificationToken.create(
            token=token,
            token_id=uuid.uuid4(),
            user_id=user_id,
            expires_at=expires_at
        )
        db.add(verification_token)

        await db.commit()
        await db.refresh(user)

        # TODO: Отправить email с токеном (mock)
        print(f"Mock email sent to {data.email} with token: {token}")

        return user, token

    @staticmethod
    async def verify_email(db: AsyncSession, data: VerifyEmailRequest) -> User:
        """Верифицирует email по токену"""
        # Найти токен
        token_hash = EmailVerificationToken.hash_token(data.token)
        stmt = select(EmailVerificationToken).where(
            EmailVerificationToken.token_hash == token_hash,
            not EmailVerificationToken.used,
            EmailVerificationToken.expires_at > datetime.now(timezone.utc)
        )
        token_obj = await db.execute(stmt)
        token_obj = token_obj.scalar_one_or_none()
        if not token_obj:
            raise ValueError("Invalid or expired token")

        # Найти пользователя
        user = await db.get(User, token_obj.user_id)
        if not user or user.email != data.email:
            raise ValueError("Invalid token for this email")

        # Подтвердить email
        user.is_email_verified = True
        token_obj.used = True

        await db.commit()
        await db.refresh(user)

        return user