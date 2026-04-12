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


@router.post(
    "/register",
    response_model=MessageResponse,
    summary="Register a new account",
    responses={409: {"description": "Email already registered"}},
)
async def register(body: RegisterRequest, service: AuthServiceDep):
    """Create a new user account.

    A confirmation email is sent to the provided address.
    The account is created immediately but `is_email_confirmed`
    remains `false` until the user calls `POST /confirm-email`
    with the token from the email.

    Returns a human-readable status message.
    """
    message = await service.register(body.email, body.password, body.nickname)
    return MessageResponse(message=message)


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Log in",
    responses={401: {"description": "Invalid credentials or account inactive"}},
)
async def login(body: LoginRequest, service: AuthServiceDep):
    """Authenticate with email and password.

    On success returns a short-lived JWT `access_token` in the JSON body
    and sets an **httponly** `refresh_token` cookie
    (path `/api/auth`, secure, samesite=strict).

    The access token should be sent in the `Authorization: Bearer <token>` header
    for all subsequent authenticated requests.
    """
    token_response, refresh_raw = await service.login(body.email, body.password)
    response = JSONResponse(content=token_response.model_dump())
    _set_refresh_cookie(response, refresh_raw)
    return response


@router.post(
    "/refresh",
    response_model=TokenResponse,
    summary="Refresh access token",
    responses={401: {"description": "Invalid or expired refresh token"}},
)
async def refresh(request: Request, service: AuthServiceDep):
    """Issue a new access token using the refresh token from the httponly cookie.

    Also rotates the refresh token itself (the old one becomes invalid).
    No request body is needed — the refresh token is read from the cookie
    set during login.
    """
    token_response, new_refresh_raw = await service.refresh(_get_refresh_token(request))
    response = JSONResponse(content=token_response.model_dump())
    _set_refresh_cookie(response, new_refresh_raw)
    return response


@router.post(
    "/logout",
    response_model=MessageResponse,
    summary="Log out",
)
async def logout(request: Request, service: AuthServiceDep):
    """Invalidate the current refresh token and clear the cookie.

    Safe to call even if no refresh token is present (idempotent).
    The access token is **not** revoked server-side — it simply expires.
    """
    token = request.cookies.get(REFRESH_COOKIE)
    if token:
        await service.logout(token)

    response = JSONResponse(content={"message": "Logged out"})
    _clear_refresh_cookie(response)
    return response


@router.post(
    "/confirm-email",
    response_model=MessageResponse,
    summary="Confirm email address",
    responses={400: {"description": "Invalid or expired token"}},
)
async def confirm_email(body: ConfirmEmailRequest, service: AuthServiceDep):
    """Confirm the user's email address using the token received via email.

    Sets `is_email_confirmed = true` on the user account.
    The token is single-use and time-limited.
    """
    await service.confirm_email(body.token)
    return MessageResponse(message="Email confirmed")


@router.post(
    "/request-password-reset",
    response_model=MessageResponse,
    summary="Request password reset",
)
async def request_password_reset(body: RequestPasswordResetRequest, service: AuthServiceDep):
    """Send a password-reset email to the given address.

    Always returns a success message regardless of whether the email
    exists in the system (to prevent user enumeration).
    """
    message = await service.request_password_reset(body.email)
    return MessageResponse(message=message)


@router.post(
    "/reset-password",
    response_model=MessageResponse,
    summary="Reset password",
    responses={400: {"description": "Invalid or expired reset token"}},
)
async def reset_password(body: ResetPasswordRequest, service: AuthServiceDep):
    """Set a new password using the reset token from the email.

    The token is single-use. After a successful reset the user must
    log in again with the new password.
    """
    await service.reset_password(body.token, body.new_password)
    return MessageResponse(message="Password reset successfully")


@router.post(
    "/resend-confirmation",
    response_model=MessageResponse,
    summary="Resend confirmation email",
)
async def resend_confirmation(body: ResendConfirmationRequest, service: AuthServiceDep):
    """Resend the email-confirmation message.

    No-op if the email is already confirmed or does not exist
    (to prevent user enumeration).
    """
    message = await service.resend_confirmation(body.email)
    return MessageResponse(message=message)


@router.get(
    "/me",
    response_model=UserResponse,
    summary="Get current user",
    responses={401: {"description": "Not authenticated"}},
)
async def get_me(user: AuthUser, service: AuthServiceDep) -> UserResponse:
    """Return the profile of the currently authenticated user.

    Requires a valid `Authorization: Bearer <access_token>` header.
    """
    user_obj = await service.get_user(user.id)
    return UserResponse.model_validate(user_obj)
