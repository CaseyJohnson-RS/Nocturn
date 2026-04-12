import uuid

from pydantic import BaseModel, Field


class SearchRequest(BaseModel):
    """Semantic search query."""

    query: str = Field(
        min_length=1, max_length=1000, description="Natural-language search query (1–1000 chars)"
    )
    limit: int = Field(default=5, ge=1, le=20, description="Max number of results to return (1–20)")


class SearchResult(BaseModel):
    """Single semantic search hit."""

    chunk_id: uuid.UUID = Field(description="ID of the matching embedding chunk")
    note_id: uuid.UUID = Field(description="Parent note ID (use to fetch the full note)")
    chunk_index: int = Field(description="Chunk position within the note (0-based)")
    content: str = Field(description="Text content of the matching chunk")
    score: float | None = Field(
        default=None, description="Cosine similarity score (higher = more relevant)"
    )


class SearchResponse(BaseModel):
    """Semantic search results."""

    results: list[SearchResult] = Field(
        description="Matching chunks ordered by relevance (highest score first)"
    )
