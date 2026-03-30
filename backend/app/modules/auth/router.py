from fastapi import APIRouter, Request, Response
from fastapi.responses import JSONResponse

from app.common.dependencies import DBSession
from app.common.exceptions import NotFoundError, UnauthorizedError
from app.config import settings
from app.middleware.auth import AuthUser
from app.modules.auth.repository import AuthRepository
from app.modules.auth.schemas import (
    ConfirmEmailRequest,
    LoginRequest,
    MessageResponse,
    RegisterRequest,
    RequestPasswordResetRequest,
    ResendConfirmationRequest,
    ResetPasswordRequest,
    TokenResponse,
    UserResponse,
)
from app.modules.auth.service import AuthService

router = APIRouter(prefix="/api/auth", tags=["auth"])

REFRESH_COOKIE = "refresh_token"


def _set_refresh_cookie(response: Response, refresh_token: str) -> None:
    response.set_cookie(
        key=REFRESH_COOKIE,
        value=refresh_token,
        httponly=True,
        secure=True,
        samesite="strict",
        max_age=settings.refresh_token_ttl_days * 86400,
        path="/api/auth",
    )


def _clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(key=REFRESH_COOKIE, path="/api/auth")


@router.post("/register", response_model=MessageResponse)
async def register(body: RegisterRequest, db: DBSession):
    service = AuthService(db)
    message = await service.register(body.email, body.password, body.nickname)
    return MessageResponse(message=message)


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, db: DBSession):
    service = AuthService(db)
    token_response, refresh_raw = await service.login(body.email, body.password)
    response = JSONResponse(content=token_response.model_dump())
    _set_refresh_cookie(response, refresh_raw)
    return response


@router.post("/refresh", response_model=TokenResponse)
async def refresh(request: Request, db: DBSession):
    refresh_token = request.cookies.get(REFRESH_COOKIE)
    if not refresh_token:
        raise UnauthorizedError("No refresh token")

    service = AuthService(db)
    token_response, new_refresh_raw = await service.refresh(refresh_token)
    response = JSONResponse(content=token_response.model_dump())
    _set_refresh_cookie(response, new_refresh_raw)
    return response


@router.post("/logout", response_model=MessageResponse)
async def logout(request: Request, db: DBSession):
    refresh_token = request.cookies.get(REFRESH_COOKIE)
    if refresh_token:
        service = AuthService(db)
        await service.logout(refresh_token)

    response = JSONResponse(content={"message": "Logged out"})
    _clear_refresh_cookie(response)
    return response


@router.post("/confirm-email", response_model=MessageResponse)
async def confirm_email(body: ConfirmEmailRequest, db: DBSession):
    service = AuthService(db)
    await service.confirm_email(body.token)
    return MessageResponse(message="Email confirmed")


@router.post("/request-password-reset", response_model=MessageResponse)
async def request_password_reset(body: RequestPasswordResetRequest, db: DBSession):
    service = AuthService(db)
    message = await service.request_password_reset(body.email)
    return MessageResponse(message=message)


@router.post("/reset-password", response_model=MessageResponse)
async def reset_password(body: ResetPasswordRequest, db: DBSession):
    service = AuthService(db)
    await service.reset_password(body.token, body.new_password)
    return MessageResponse(message="Password reset successfully")


@router.post("/resend-confirmation", response_model=MessageResponse)
async def resend_confirmation(body: ResendConfirmationRequest, db: DBSession):
    service = AuthService(db)
    message = await service.resend_confirmation(body.email)
    return MessageResponse(message=message)


@router.get("/me", response_model=UserResponse)
async def get_me(user: AuthUser, db: DBSession):
    repo = AuthRepository(db)
    db_user = await repo.get_user_by_id(user.id)
    if not db_user:
        raise NotFoundError("User not found")
    return db_user
