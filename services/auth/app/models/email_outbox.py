import uuid

from datetime import datetime

from sqlalchemy import ForeignKey, Integer, String, DateTime, Enum, func
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
import enum

from .base import Base


class EmailStatus(str, enum.Enum):
    pending = "pending"
    sent = "sent"
    failed = "failed"


class EmailOutbox(Base):
    __tablename__ = "email_outbox"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.user_id"),
        nullable=False,
        index=True
    )
    email_type: Mapped[str] = mapped_column(
        String(255),
        nullable=False
    )
    email: Mapped[str] = mapped_column(
        String(255),
        nullable=False
    )
    payload: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False
    )
    status: Mapped[EmailStatus] = mapped_column(
        Enum(EmailStatus, name="email_status_enum"),
        default=EmailStatus.pending,
        nullable=False
    )
    attempts: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0
    )
    last_error: Mapped[str] = mapped_column(
        String(512),
        nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=func.now(),
        nullable=False
    )
    sent_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )

    user: Mapped["User"] = relationship(  # noqa: F821 # type: ignore
        "User",
        back_populates="email_outbox"
    )

    @classmethod
    def create(
        cls,
        user_id: uuid.UUID,
        email_type: str,
        email: str,
        payload: dict,
        status: EmailStatus = EmailStatus.pending,
        attempts: int = 0,
    ) -> "EmailOutbox":
        return cls(
            user_id=user_id,
            email_type=email_type,
            email=email,
            payload=payload,
            status=status,
            attempts=attempts
        )
