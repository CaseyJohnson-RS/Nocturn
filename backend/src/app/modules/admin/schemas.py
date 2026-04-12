import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class UserListItem(BaseModel):
    """User record visible to admins."""

    id: uuid.UUID = Field(description="User ID")
    email: str = Field(description="User email")
    nickname: str = Field(description="Display name")
    role: str = Field(description="Role: `user` or `admin`")
    is_email_confirmed: bool = Field(description="Whether the email is confirmed")
    is_active: bool = Field(description="Whether the account is active")
    created_at: datetime = Field(description="Registration timestamp (UTC)")

    model_config = {"from_attributes": True}


class UserListResponse(BaseModel):
    """Paginated list of users (admin view)."""

    items: list[UserListItem] = Field(description="Users on this page")
    total: int = Field(description="Total number of users")
    limit: int = Field(description="Requested page size")
    offset: int = Field(description="Requested offset")


class SetActiveRequest(BaseModel):
    """Enable or disable a user account."""

    is_active: bool = Field(description="`true` to activate, `false` to deactivate")


class SetRoleRequest(BaseModel):
    """Change a user's role."""

    role: str = Field(pattern=r"^(user|admin)$", description="New role: `user` or `admin`")
