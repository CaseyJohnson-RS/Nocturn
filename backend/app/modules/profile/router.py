from fastapi import APIRouter

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


@router.put("/nickname", response_model=UserResponse)
async def update_nickname(body: UpdateNicknameRequest, user: AuthUser, db: DBSession):
    service = ProfileService(db)
    return await service.update_nickname(user.id, body.nickname)


@router.put("/password", response_model=MessageResponse)
async def change_password(body: ChangePasswordRequest, user: AuthUser, db: DBSession):
    service = ProfileService(db)
    await service.change_password(user.id, body.current_password, body.new_password)
    return MessageResponse(message="Password changed successfully")


@router.post("/deactivate", status_code=204)
async def delete_account(body: DeleteAccountRequest, user: AuthUser, db: DBSession):
    service = ProfileService(db)
    await service.delete_account(user.id, body.password)
