import uuid

from datetime import datetime

from sqlalchemy import DateTime, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base_token import BaseToken


class RefreshToken(BaseToken):
    __tablename__ = "refresh_tokens"
    
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )
    replaced_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=func.now(),
        nullable=False
    )

    user: Mapped["User"] = relationship(  # noqa: F821 # type: ignore
        "User",
        back_populates="refresh_tokens"
    )

    @classmethod
    def create(
        cls,
        token_hash: str,
        user_id: uuid.UUID,
        expires_at: datetime,
        replaced_by_id: uuid.UUID = None
    ):
        return cls(
            id=uuid.uuid4(),
            token_hash=token_hash,
            user_id=user_id,
            expires_at=expires_at,
            revoked_at=None,
            replaced_by_id=replaced_by_id,
        )
