from sqlalchemy import Boolean
from sqlalchemy.orm import relationship, Mapped, mapped_column
from datetime import datetime
import uuid
from .base_token import BaseToken


class EmailVerificationToken(BaseToken):
    __tablename__ = "email_verification_tokens"

    used: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False
    )

    user: Mapped["User"] = relationship(  # noqa: F821 # type: ignore
        "User", back_populates="email_verification_tokens"
    )

    @classmethod
    def create(cls, token: str, user_id: uuid.UUID, expires_at: datetime):
        return cls(
            token_hash=cls.hash_token(token),
            user_id=user_id,
            expires_at=expires_at,
        )
