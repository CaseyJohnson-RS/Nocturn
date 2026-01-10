from sqlalchemy import Column, String, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime
from .base_token import BaseToken


class EmailVerificationToken(BaseToken):
    __tablename__ = "email_verification_tokens"
    token_id = Column(String, primary_key=True)
    used = Column(Boolean, default=False, nullable=False)

    user = relationship("User", back_populates="email_verification_tokens")

    @classmethod
    def create(cls, token: str, token_id: str, user_id: str, expires_at: datetime):
        return cls(
            token_id=token_id,
            token_hash=cls.hash_token(token),
            user_id=user_id,
            expires_at=expires_at,
            used=False
        )