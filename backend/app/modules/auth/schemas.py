import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field

# --- Requests ---


class RegisterRequest(BaseModel):
    """New user registration data."""

    email: EmailStr = Field(description="User email address (used for login)")
    password: str = Field(min_length=8, max_length=128, description="Password (8–128 characters)")
    nickname: str = Field(min_length=2, max_length=32, description="Display name (2–32 characters)")


class LoginRequest(BaseModel):
    """Login credentials."""

    email: EmailStr = Field(description="Registered email address")
    password: str = Field(description="Account password")


class RefreshRequest(BaseModel):
    """Refresh token is read from the httponly cookie — no body needed."""

    pass


class ConfirmEmailRequest(BaseModel):
    """Email confirmation payload."""

    token: str = Field(description="Single-use confirmation token from the email")


class RequestPasswordResetRequest(BaseModel):
    """Password reset initiation."""

    email: EmailStr = Field(description="Email address to send the reset link to")


class ResetPasswordRequest(BaseModel):
    """Password reset completion."""

    token: str = Field(description="Single-use reset token from the email")
    new_password: str = Field(
        min_length=8, max_length=128, description="New password (8–128 characters)"
    )


class ResendConfirmationRequest(BaseModel):
    """Resend confirmation email."""

    email: EmailStr = Field(description="Email address to resend confirmation to")


# --- Responses ---


class MessageResponse(BaseModel):
    """Generic text response."""

    message: str = Field(description="Human-readable status message")


class TokenResponse(BaseModel):
    """JWT access token."""

    access_token: str = Field(
        description="Short-lived JWT token for `Authorization: Bearer` header"
    )
    token_type: str = Field(default="bearer", description="Always `bearer`")


class UserResponse(BaseModel):
    """User profile."""

    id: uuid.UUID = Field(description="Unique user identifier")
    email: str = Field(description="User email")
    nickname: str = Field(description="Display name")
    role: str = Field(description="Role: `user` or `admin`")
    is_email_confirmed: bool = Field(description="Whether the email has been confirmed")
    is_active: bool = Field(description="Whether the account is active (can log in)")
    created_at: datetime = Field(description="Account creation timestamp (UTC)")

    model_config = {"from_attributes": True}
