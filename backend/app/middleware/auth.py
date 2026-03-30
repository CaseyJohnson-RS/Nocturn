import uuid
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, Request

from app.common.exceptions import ForbiddenError, UnauthorizedError
from app.modules.auth.service import AuthService


@dataclass
class CurrentUser:
    id: uuid.UUID
    role: str


def get_current_user(request: Request) -> CurrentUser:
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise UnauthorizedError("Missing or invalid authorization header")

    token = auth_header.removeprefix("Bearer ")
    payload = AuthService.decode_access_token(token)

    return CurrentUser(
        id=uuid.UUID(payload["sub"]),
        role=payload["role"],
    )


def require_admin(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
    if user.role != "admin":
        raise ForbiddenError("Admin access required")
    return user


AuthUser = Annotated[CurrentUser, Depends(get_current_user)]
AdminUser = Annotated[CurrentUser, Depends(require_admin)]
