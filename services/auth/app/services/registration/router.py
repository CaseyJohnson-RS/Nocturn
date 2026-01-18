from fastapi import APIRouter, Depends, HTTPException

from app.core.dependencies import get_request_context, RequestContext

from app.services.registration.schemas import (
    RegisterUserSchema,
    VerifyEmailRequest,
)

from app.services.schemas import StatusResponse

from app.services.registration.service import RegistrationService

from app.services.registration.exceptions import (
    RegistrationError,
    UserAlreadyExists,
    InvalidEmailToken,
    ExpiredEmailToken,
    EmailDoesNotMatchToken,
)


router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=StatusResponse)
async def register_user(data: RegisterUserSchema, context: RequestContext = Depends(get_request_context)):
    try:
        await RegistrationService.register_user(data)
        return StatusResponse(status="success")
    except RegistrationError as e:
        if isinstance(e, UserAlreadyExists):
            pass
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/verify-email", response_model=StatusResponse)
async def verify_email(data: VerifyEmailRequest, context: RequestContext = Depends(get_request_context)):
    try:
        await RegistrationService.verify_email(data)
        return StatusResponse(status="success")
    except RegistrationError as e:
        if isinstance(e, InvalidEmailToken):
            pass
        elif isinstance(e, ExpiredEmailToken):
            pass
        elif isinstance(e, EmailDoesNotMatchToken):
            pass
        raise HTTPException(status_code=400, detail=str(e))
