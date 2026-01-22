from uuid import UUID
from pydantic import BaseModel, EmailStr


class VerifyEmailInputDTO(BaseModel):
    email: EmailStr
    token: str


class VerifyEmailOutputDTO(BaseModel):
    id: UUID
    email: str
    token_used: bool
