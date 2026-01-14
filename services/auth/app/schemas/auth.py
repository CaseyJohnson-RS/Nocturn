from pydantic import BaseModel, EmailStr, Field
from typing import Optional

class RegisterUserSchema(BaseModel):
    email: EmailStr
    username: Optional[str] = Field(default="Unknown", max_length=50)
    password: str = Field(min_length=8)

class VerifyEmailRequest(BaseModel):
    email: EmailStr
    token: str

class RegisterResponse(BaseModel):
    message: str
    user_id: str

class VerifyEmailResponse(BaseModel):
    message: str
    email_verified: bool

