from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import JSONResponse

from app.common.dependencies import DBSession
from app.common.exceptions import UnauthorizedError
from app.config import settings
from app.middleware.auth import AuthUser
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


# --- Dependencies ---


async def get_auth_service(db: DBSession) -> AuthService:
    return AuthService(db)


AuthServiceDep = Annotated[AuthService, Depends(get_auth_service)]


# --- Helpers ---


def _set_refresh_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=REFRESH_COOKIE,
        value=token,
        httponly=True,
        secure=True,
        samesite="strict",
        max_age=settings.refresh_token_ttl_days * 86400,
        path="/api/auth",
    )


def _clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(key=REFRESH_COOKIE, path="/api/auth")


def _get_refresh_token(request: Request) -> str:
    token = request.cookies.get(REFRESH_COOKIE)
    if not token:
        raise UnauthorizedError("No refresh token")
    return token


# --- Endpoints ---


@router.post("/register", response_model=MessageResponse)
async def register(body: RegisterRequest, service: AuthServiceDep):
    message = await service.register(body.email, body.password, body.nickname)
    return MessageResponse(message=message)


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, service: AuthServiceDep):
    token_response, refresh_raw = await service.login(body.email, body.password)
    response = JSONResponse(content=token_response.model_dump())
    _set_refresh_cookie(response, refresh_raw)
    return response


@router.post("/refresh", response_model=TokenResponse)
async def refresh(request: Request, service: AuthServiceDep):
    token_response, new_refresh_raw = await service.refresh(_get_refresh_token(request))
    response = JSONResponse(content=token_response.model_dump())
    _set_refresh_cookie(response, new_refresh_raw)
    return response


@router.post("/logout", response_model=MessageResponse)
async def logout(request: Request, service: AuthServiceDep):
    token = request.cookies.get(REFRESH_COOKIE)
    if token:
        await service.logout(token)

    response = JSONResponse(content={"message": "Logged out"})
    _clear_refresh_cookie(response)
    return response


@router.post("/confirm-email", response_model=MessageResponse)
async def confirm_email(body: ConfirmEmailRequest, service: AuthServiceDep):
    await service.confirm_email(body.token)
    return MessageResponse(message="Email confirmed")


@router.post("/request-password-reset", response_model=MessageResponse)
async def request_password_reset(body: RequestPasswordResetRequest, service: AuthServiceDep):
    message = await service.request_password_reset(body.email)
    return MessageResponse(message=message)


@router.post("/reset-password", response_model=MessageResponse)
async def reset_password(body: ResetPasswordRequest, service: AuthServiceDep):
    await service.reset_password(body.token, body.new_password)
    return MessageResponse(message="Password reset successfully")


@router.post("/resend-confirmation", response_model=MessageResponse)
async def resend_confirmation(body: ResendConfirmationRequest, service: AuthServiceDep):
    message = await service.resend_confirmation(body.email)
    return MessageResponse(message=message)


@router.get("/me", response_model=UserResponse)
async def get_me(user: AuthUser, service: AuthServiceDep) -> UserResponse:
    user_obj = await service.get_user(user.id)
    return UserResponse.model_validate(user_obj)
