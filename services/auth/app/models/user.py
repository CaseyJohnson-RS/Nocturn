import uuid

from datetime import datetime

from sqlalchemy import Boolean, DateTime, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship


from .base import Base
from .email_verification_token import EmailVerificationToken
from .password_reset_token import PasswordResetToken
from .refresh_token import RefreshToken
from .security_event import SecurityEvent
from .sent_email import SentEmail


class User(Base):
    __tablename__ = "users"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True
    )
    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False,
        index=True
    )
    is_email_verified: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False
    )
    password_hash: Mapped[str] = mapped_column(
        String(255),
        nullable=False
    )
    username: Mapped[str] = mapped_column(
        String(50),
        default="Unknown",
        unique=False,
        nullable=False
    )
    status: Mapped[str] = mapped_column(
        String(255),
        default="active",
        nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=func.now(),
        nullable=False
    )

    security_events: Mapped[list[SecurityEvent]] = relationship(
        SecurityEvent,
        back_populates="user",
        cascade="all, delete-orphan"
    )
    password_reset_tokens: Mapped[list[PasswordResetToken]] = relationship(
        PasswordResetToken,
        back_populates="user",
        cascade="all, delete-orphan"
    )
    email_verification_tokens: Mapped[list[EmailVerificationToken]] = relationship(
        EmailVerificationToken,
        back_populates="user",
        cascade="all, delete-orphan"
    )
    refresh_tokens: Mapped[list[RefreshToken]] = relationship(
        RefreshToken,
        back_populates="user",
        cascade="all, delete-orphan"
    )
    sent_emails: Mapped[list[SentEmail]] = relationship(
        SentEmail,
        back_populates="user",
        cascade="all, delete-orphan"
    )

    @classmethod
    def create(cls, email: str, password_hash: str, username: str = "Unknown") -> "User":
        return cls(
            user_id=uuid.uuid4(),
            email=email,
            password_hash=password_hash,
            username=username
        )
