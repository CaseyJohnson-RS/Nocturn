from pydantic import BaseModel, Field


class UpdateNicknameRequest(BaseModel):
    """Payload for changing the display nickname."""

    nickname: str = Field(
        min_length=2, max_length=32, description="New display name (2–32 characters)"
    )


class ChangePasswordRequest(BaseModel):
    """Payload for changing the account password."""

    current_password: str = Field(description="Current password for verification")
    new_password: str = Field(
        min_length=8, max_length=128, description="New password (8–128 characters)"
    )


class DeleteAccountRequest(BaseModel):
    """Payload for permanent account deletion."""

    password: str = Field(description="Account password for confirmation")
