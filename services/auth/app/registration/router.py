from fastapi import APIRouter, HTTPException

from app.registration.schemas import (
    RegisterUserSchema,
    VerifyEmailRequest,
    StatusResponce
)

from app.registration.service import RegistrationService


router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=StatusResponce)
async def register_user(data: RegisterUserSchema):
    try:
        await RegistrationService.register_user(data)
        return StatusResponce(status="success")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/verify-email", response_model=StatusResponce)
async def verify_email(data: VerifyEmailRequest):
    try:
        await RegistrationService.verify_email(data)
        return StatusResponce(status="success")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
