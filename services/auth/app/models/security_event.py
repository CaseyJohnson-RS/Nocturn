from sqlalchemy import Column, String, DateTime
from sqlalchemy.dialects.postgresql import UUID
from datetime import datetime, timezone
from sqlalchemy.orm import relationship
from app.models.base import Base
from sqlalchemy import ForeignKey
import uuid

class SecurityEvent(Base):
    __tablename__ = "security_events"

    event_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.user_id"), nullable=False, index=True)
    event_type = Column(String, nullable=False)
    ip_address = Column(String, nullable=True)  # inet можно использовать через postgresql specific
    user_agent = Column(String, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    user = relationship("User", back_populates="security_events")
