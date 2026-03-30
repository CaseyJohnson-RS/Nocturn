from pydantic import BaseModel, Field


class UpdateNicknameRequest(BaseModel):
    nickname: str = Field(min_length=2, max_length=32, pattern=r"^[a-zA-Zа-яА-ЯёЁ0-9_-]+$")


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8, max_length=128)


class DeleteAccountRequest(BaseModel):
    password: str
