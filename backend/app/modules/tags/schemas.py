import uuid
from datetime import datetime

from pydantic import BaseModel, Field

# --- Requests ---


class CreateTagRequest(BaseModel):
    """Payload for creating a new tag."""

    name: str = Field(
        min_length=1, max_length=50, description="Tag name (1–50 chars, unique per user)"
    )


class UpdateTagRequest(BaseModel):
    """Payload for renaming a tag."""

    name: str = Field(
        min_length=1, max_length=50, description="New tag name (1–50 chars, must be unique)"
    )


# --- Responses ---


class TagResponse(BaseModel):
    """Full tag object."""

    id: uuid.UUID = Field(description="Tag ID")
    user_id: uuid.UUID = Field(description="Owner user ID")
    name: str = Field(description="Tag display name")
    created_at: datetime = Field(description="Creation timestamp (UTC)")

    model_config = {"from_attributes": True}


class TagListResponse(BaseModel):
    """Paginated list of tags."""

    items: list[TagResponse] = Field(description="Tags on this page")
    total: int = Field(description="Total number of matching tags")
    limit: int = Field(description="Requested page size")
    offset: int = Field(description="Requested offset")
