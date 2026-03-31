"""Create note_chunks and embedding_queue tables for RAG

Revision ID: 003
Revises: 002
Create Date: 2026-03-31

"""
from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects.postgresql import UUID

revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

DIMS = 2560


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "note_chunks",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("note_id", UUID(as_uuid=True), sa.ForeignKey("notes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("chunk_index", sa.Integer, nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("embedding", Vector(DIMS), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("idx_chunks_note", "note_chunks", ["note_id"])
    op.create_index("idx_chunks_user", "note_chunks", ["user_id"])

    op.create_table(
        "embedding_queue",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("note_id", UUID(as_uuid=True), sa.ForeignKey("notes.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("attempts", sa.Integer, nullable=False, server_default=sa.text("0")),
        sa.Column("status", sa.String(20), nullable=False, server_default=sa.text("'pending'")),
        sa.Column("error", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("idx_eq_status", "embedding_queue", ["status"])


def downgrade() -> None:
    op.drop_table("embedding_queue")
    op.drop_table("note_chunks")
    op.execute("DROP EXTENSION IF EXISTS vector")
