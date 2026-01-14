import hashlib
import uuid

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class BaseToken(Base):
    __abstract__ = True

    token_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )
    token_hash: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.user_id"),
        nullable=False,
        index=True
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
    )

    @staticmethod
    def hash_token(token: str) -> str:
        """Returns the SHA-256 hash of the given token"""
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    def verify_token(self, token: str) -> bool:
        """Checks if the hash of the given token matches the stored hash"""
        return self.token_hash == self.hash_token(token)