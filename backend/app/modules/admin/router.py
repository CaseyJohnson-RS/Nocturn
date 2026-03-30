import uuid

from fastapi import APIRouter, Query

from app.common.dependencies import DBSession
from app.middleware.auth import AdminUser
from app.modules.admin.schemas import (
    SetActiveRequest,
    SetRoleRequest,
    UserListItem,
    UserListResponse,
)
from app.modules.admin.service import AdminService

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.get("/users", response_model=UserListResponse)
async def list_users(
    admin: AdminUser,
    db: DBSession,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    search: str | None = Query(default=None),
):
    service = AdminService(db)
    return await service.list_users(limit, offset, search)


@router.get("/users/{user_id}", response_model=UserListItem)
async def get_user(user_id: uuid.UUID, admin: AdminUser, db: DBSession):
    service = AdminService(db)
    return await service.get_user(user_id)


@router.put("/users/{user_id}/active", response_model=UserListItem)
async def set_active(
    user_id: uuid.UUID, body: SetActiveRequest, admin: AdminUser, db: DBSession
):
    service = AdminService(db)
    return await service.set_active(admin.id, user_id, body.is_active)


@router.put("/users/{user_id}/role", response_model=UserListItem)
async def set_role(
    user_id: uuid.UUID, body: SetRoleRequest, admin: AdminUser, db: DBSession
):
    service = AdminService(db)
    return await service.set_role(admin.id, user_id, body.role)
