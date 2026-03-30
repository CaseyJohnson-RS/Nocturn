import uuid
from datetime import datetime

from pydantic import BaseModel, Field


# --- Requests ---

class CreateTagRequest(BaseModel):
    name: str = Field(min_length=1, max_length=50)


class UpdateTagRequest(BaseModel):
    name: str = Field(min_length=1, max_length=50)


# --- Responses ---

class TagResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    name: str
    created_at: datetime

    model_config = {"from_attributes": True}


class TagListResponse(BaseModel):
    items: list[TagResponse]
    total: int
    limit: int
    offset: int
