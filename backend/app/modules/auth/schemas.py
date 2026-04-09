import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field

# --- Requests ---


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    nickname: str = Field(min_length=2, max_length=32)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class RefreshRequest(BaseModel):
    pass  # Refresh token comes from cookie


class ConfirmEmailRequest(BaseModel):
    token: str


class RequestPasswordResetRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str = Field(min_length=8, max_length=128)


class ResendConfirmationRequest(BaseModel):
    email: EmailStr


# --- Responses ---


class MessageResponse(BaseModel):
    message: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    id: uuid.UUID
    email: str
    nickname: str
    role: str
    is_email_confirmed: bool
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}
