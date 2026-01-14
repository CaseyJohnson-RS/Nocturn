from sqlalchemy import Column, String, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from app.models.base import Base
import hashlib

class BaseToken(Base):
    __abstract__ = True
    token_hash = Column(String, nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.user_id"), nullable=False, index=True)
    expires_at = Column(DateTime, nullable=False)

    @staticmethod
    def hash_token(token: str) -> str:
        """Возвращает SHA-256 хеш токена в виде hex строки"""
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    def verify_token(self, token: str) -> bool:
        """Проверяет, совпадает ли хеш переданного токена с сохранённым"""
        return self.token_hash == self.hash_token(token)