from pydantic import BaseModel, EmailStr, Field

class RegisterUserSchema(BaseModel):
    email: EmailStr
    username: str = Field(
        default="Unknown",
        max_length=50,
        min_length=1
    )
    password: str = Field(min_length=8)

class VerifyEmailRequest(BaseModel):
    email: EmailStr
    token: str
