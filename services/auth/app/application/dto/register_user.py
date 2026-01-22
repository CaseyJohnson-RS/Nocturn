from pydantic import BaseModel, EmailStr, Field
from uuid import UUID


class RegisterUserInputDTO(BaseModel):
    email: EmailStr
    username: str = Field(default="Unknown", max_length=50, min_length=1)
    password: str = Field(min_length=8)


class RegisterUserOutputDTO(BaseModel):
    id: UUID
    email: str
    verification_email_enqueued: bool
