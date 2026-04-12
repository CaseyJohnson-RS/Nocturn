import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query

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


async def get_admin_service(db: DBSession) -> AdminService:
    return AdminService(db)


AdminServiceDep = Annotated[AdminService, Depends(get_admin_service)]


@router.get(
    "/users",
    response_model=UserListResponse,
    summary="List all users",
    responses={403: {"description": "Not an admin"}},
)
async def list_users(
    _: AdminUser,
    service: AdminServiceDep,
    limit: int = Query(default=50, ge=1, le=100, description="Max number of users"),
    offset: int = Query(default=0, ge=0, description="Number of users to skip"),
    search: str | None = Query(default=None, description="Search by email or nickname"),
):
    """Return a paginated list of all users in the system.

    **Admin only.** Supports optional search by email or nickname substring.
    """
    return await service.list_users(limit, offset, search)


@router.get(
    "/users/{user_id}",
    response_model=UserListItem,
    summary="Get a user",
    responses={
        403: {"description": "Not an admin"},
        404: {"description": "User not found"},
    },
)
async def get_user(user_id: uuid.UUID, _: AdminUser, service: AdminServiceDep):
    """Return a single user's details by ID. **Admin only.**"""
    return await service.get_user(user_id)


@router.put(
    "/users/{user_id}/active",
    response_model=UserListItem,
    summary="Enable / disable a user",
    responses={
        403: {"description": "Not an admin or trying to deactivate yourself"},
        404: {"description": "User not found"},
    },
)
async def set_active(
    user_id: uuid.UUID,
    body: SetActiveRequest,
    admin: AdminUser,
    service: AdminServiceDep,
):
    """Set a user's `is_active` flag. **Admin only.**

    Deactivated users cannot log in or use the API.
    An admin cannot deactivate their own account.
    """
    return await service.set_active(admin.id, user_id, body.is_active)


@router.put(
    "/users/{user_id}/role",
    response_model=UserListItem,
    summary="Change a user's role",
    responses={
        403: {"description": "Not an admin or trying to change own role"},
        404: {"description": "User not found"},
    },
)
async def set_role(
    user_id: uuid.UUID,
    body: SetRoleRequest,
    admin: AdminUser,
    service: AdminServiceDep,
):
    """Change a user's role to `user` or `admin`. **Admin only.**

    An admin cannot change their own role.
    """
    return await service.set_role(admin.id, user_id, body.role)
