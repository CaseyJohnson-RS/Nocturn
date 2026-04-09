from typing import Annotated

from fastapi import APIRouter, Depends

from app.common.dependencies import DBSession
from app.middleware.auth import AuthUser
from app.modules.auth.schemas import MessageResponse, UserResponse
from app.modules.profile.schemas import (
    ChangePasswordRequest,
    DeleteAccountRequest,
    UpdateNicknameRequest,
)
from app.modules.profile.service import ProfileService

router = APIRouter(prefix="/api/profile", tags=["profile"])


async def get_profile_service(db: DBSession) -> ProfileService:
    return ProfileService(db)


ProfileServiceDep = Annotated[ProfileService, Depends(get_profile_service)]


@router.put("/nickname", response_model=UserResponse)
async def update_nickname(body: UpdateNicknameRequest, user: AuthUser, service: ProfileServiceDep):
    return await service.update_nickname(user.id, body.nickname)


@router.put("/password", response_model=MessageResponse)
async def change_password(body: ChangePasswordRequest, user: AuthUser, service: ProfileServiceDep):
    await service.change_password(user.id, body.current_password, body.new_password)
    return MessageResponse(message="Password changed successfully")


@router.post("/delete_account", status_code=204)
async def delete_account(body: DeleteAccountRequest, user: AuthUser, service: ProfileServiceDep):
    await service.delete_account(user.id, body.password)