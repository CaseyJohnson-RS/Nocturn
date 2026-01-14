import uuid

from datetime import datetime, timezone

from sqlalchemy import String, DateTime
from sqlalchemy.dialects.postgresql import UUID, INET
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base_token import BaseToken


class RefreshToken(BaseToken):
    __tablename__ = "refresh_tokens"
    
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True
    )
    replaced_by_token_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )
    user_agent: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True
    )
    ip_address: Mapped[str | None] = mapped_column(
        INET(),
        nullable=True
    )

    user: Mapped["User"] = relationship(  # noqa: F821 # type: ignore
        "User",
        back_populates="refresh_tokens"
    )

    @classmethod
    def create(cls, token: str, user_id: uuid.UUID, expires_at: datetime,
               user_agent: str = None, ip_address: str = None, replaced_by_token_id: uuid.UUID = None):
        return cls(
            token_hash=cls.hash_token(token),
            user_id=user_id,
            expires_at=expires_at,
            revoked_at=None,
            replaced_by_token_id=replaced_by_token_id,
            created_at=datetime.now(timezone.utc),
            user_agent=user_agent,
            ip_address=ip_address
        )
