from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.deps import get_db
from app.schemas.auth import RegisterUserSchema, VerifyEmailRequest, RegisterResponse, VerifyEmailResponse
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])

@router.post("/register", response_model=RegisterResponse)
async def register_user(data: RegisterUserSchema, db: AsyncSession = Depends(get_db)):
    try:
        user, _ = await AuthService.register_user(db, data)
        return RegisterResponse(message="Registration successful. Check your email for verification.", user_id=user.user_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/verify-email", response_model=VerifyEmailResponse)
async def verify_email(data: VerifyEmailRequest, db: AsyncSession = Depends(get_db)):
    try:
        user = await AuthService.verify_email(db, data)
        return VerifyEmailResponse(message="Email verified successfully.", email_verified=True)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))