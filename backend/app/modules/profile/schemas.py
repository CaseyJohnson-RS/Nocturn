from pydantic import BaseModel, Field


class UpdateNicknameRequest(BaseModel):
    nickname: str = Field(min_length=2, max_length=32)


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8, max_length=128)


class DeleteAccountRequest(BaseModel):
    password: str
