import uuid

from datetime import datetime

from sqlalchemy import ForeignKey, String, DateTime, func
from sqlalchemy.dialects.postgresql import UUID, INET
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base


class SecurityEvent(Base):
    __tablename__ = "security_events"

    event_id: Mapped[uuid.UUID] = mapped_column(
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
    event_type: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        unique=False,
        index=False
    )
    ip_address: Mapped[str | None] = mapped_column(
        INET(),
        nullable=True,
        unique=False,
        index=False
    )
    user_agent: Mapped[str | None] = mapped_column(
        String(512),
        nullable=True,
        unique=False,
        index=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=func.now(),
        nullable=False,
        unique=False,
        index=False,
    )

    user: Mapped["User"] = relationship(  # noqa: F821 # type: ignore
        "User",
        back_populates="security_events"
    )

    @classmethod
    def create(
        cls,
        user_id: uuid.UUID,
        event_type: str,
        ip_address: str | None = None,
        user_agent: str | None = None
    ) -> "SecurityEvent":
        return cls(
            event_id=uuid.uuid4(),
            user_id=user_id,
            event_type=event_type,
            ip_address=ip_address,
            user_agent=user_agent
        )
