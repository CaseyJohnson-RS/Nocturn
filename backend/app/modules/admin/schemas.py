import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class UserListItem(BaseModel):
    id: uuid.UUID
    email: str
    nickname: str
    role: str
    is_email_confirmed: bool
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class UserListResponse(BaseModel):
    items: list[UserListItem]
    total: int
    limit: int
    offset: int


class SetActiveRequest(BaseModel):
    is_active: bool


class SetRoleRequest(BaseModel):
    role: str = Field(pattern=r"^(user|admin)$")
