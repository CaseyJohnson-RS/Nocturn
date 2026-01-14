from sqlalchemy import Column, String, DateTime
from sqlalchemy.dialects.postgresql import UUID
from app.models.base_token import BaseToken
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
import uuid


class RefreshToken(BaseToken):
    __tablename__ = "refresh_tokens"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    revoked_at = Column(DateTime, nullable=True)
    replaced_by_token_id = Column(String, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    user_agent = Column(String, nullable=True)
    ip_address = Column(String, nullable=True)

    user = relationship("User", back_populates="refresh_tokens")

    @classmethod
    def create(cls, token: str, id: uuid.UUID, user_id: uuid.UUID, expires_at: datetime,
               user_agent: str = None, ip_address: str = None, replaced_by_token_id: str = None):
        return cls(
            id=id,
            token_hash=cls.hash_token(token),
            user_id=user_id,
            expires_at=expires_at,
            revoked_at=None,
            replaced_by_token_id=replaced_by_token_id,
            created_at=datetime.now(timezone.utc),
            user_agent=user_agent,
            ip_address=ip_address
        )