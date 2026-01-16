import uuid

from datetime import datetime

from sqlalchemy import Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base_token import BaseToken


class PasswordResetToken(BaseToken):
    __tablename__ = "password_reset_tokens"
    
    used: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False
    )

    user: Mapped["User"] = relationship(  # noqa: F821 # type: ignore
        "User",
        back_populates="password_reset_tokens"
    )

    @classmethod
    def create(cls, token_hash: str, user_id: uuid.UUID, expires_at: datetime):
        return cls(
            token_hash=token_hash,
            user_id=user_id,
            expires_at=expires_at,
        )
