from .base_token import BaseToken
from sqlalchemy import Column, String, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime


class PasswordResetToken(BaseToken):
    __tablename__ = "password_reset_tokens"
    token_hash = Column(String, primary_key=True)
    used = Column(Boolean, default=False, nullable=False)

    user = relationship("User", back_populates="password_reset_tokens")

    @classmethod
    def create(cls, token: str, user_id: str, expires_at: datetime):
        return cls(
            token_hash=cls.hash_token(token),
            user_id=user_id,
            expires_at=expires_at,
            used=False
        )