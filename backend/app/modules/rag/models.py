import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.common.database import Base
from app.config import settings


class NoteChunk(Base):
    __tablename__ = "note_chunks"
    __table_args__ = (
        Index("idx_chunks_note", "note_id"),
        Index("idx_chunks_user", "user_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    note_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("notes.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    embedding = mapped_column(Vector(settings.embedding_dimensions), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class EmbeddingTask(Base):
    __tablename__ = "embedding_queue"
    __table_args__ = (
        Index("idx_eq_status", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    note_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("notes.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
