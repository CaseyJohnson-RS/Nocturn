from fastapi import APIRouter, HTTPException, Depends

from app.services.registration.schemas import (
    RegisterUserSchema,
    VerifyEmailRequest
)
from app.services.schemas import StatusResponce

from app.core.dependencies import get_request_context, RequestContext
from app.services.registration.service import RegistrationService


router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=StatusResponce)
async def register_user(data: RegisterUserSchema, context: RequestContext = Depends(get_request_context)):
    try:
        await RegistrationService.register_user(data)
        return StatusResponce(status="success")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/verify-email", response_model=StatusResponce)
async def verify_email(data: VerifyEmailRequest, context: RequestContext = Depends(get_request_context)):
    try:
        await RegistrationService.verify_email(data)
        return StatusResponce(status="success")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
