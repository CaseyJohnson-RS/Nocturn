from typing import Annotated

from fastapi import APIRouter, Depends

from src.app.common.dependencies import DBSession
from src.app.middleware.auth import AuthUser
from src.app.modules.auth.schemas import MessageResponse, UserResponse
from src.app.modules.profile.schemas import (
    ChangePasswordRequest,
    DeleteAccountRequest,
    UpdateNicknameRequest,
)
from src.app.modules.profile.service import ProfileService

router = APIRouter(prefix="/api/profile", tags=["profile"])


async def get_profile_service(db: DBSession) -> ProfileService:
    return ProfileService(db)


ProfileServiceDep = Annotated[ProfileService, Depends(get_profile_service)]


@router.put(
    "/nickname",
    response_model=UserResponse,
    summary="Change nickname",
)
async def update_nickname(body: UpdateNicknameRequest, user: AuthUser, service: ProfileServiceDep):
    """Update the current user's display nickname.

    The nickname must be 2–32 characters long. Returns the full
    updated user profile.
    """
    return await service.update_nickname(user.id, body.nickname)


@router.put(
    "/password",
    response_model=MessageResponse,
    summary="Change password",
    responses={
        400: {"description": "Current password is incorrect"},
    },
)
async def change_password(body: ChangePasswordRequest, user: AuthUser, service: ProfileServiceDep):
    """Change the current user's password.

    Requires the current password for verification. The new password
    must be 8–128 characters. Existing sessions remain valid —
    the user is not logged out.
    """
    await service.change_password(user.id, body.current_password, body.new_password)
    return MessageResponse(message="Password changed successfully")


@router.post(
    "/delete_account",
    status_code=204,
    summary="Delete account",
    responses={
        400: {"description": "Password is incorrect"},
    },
)
async def delete_account(body: DeleteAccountRequest, user: AuthUser, service: ProfileServiceDep):
    """Permanently delete the current user's account and all associated data.

    Requires the account password for confirmation.
    This action is **irreversible** — all notes, tags, chat sessions,
    and embeddings are removed.
    """
    await service.delete_account(user.id, body.password)
