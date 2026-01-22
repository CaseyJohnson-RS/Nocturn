from fastapi import APIRouter, Depends, HTTPException
from app.application.dto.verify_email import VerifyEmailInputDTO, VerifyEmailOutputDTO
from app.adapters.inbound.http.dependencies import get_verify_email_service
from app.application.use_cases.verify_email import VerifyEmailService
from app.domain.exceptions import DomainError

router = APIRouter()

@router.post("/", response_model=VerifyEmailOutputDTO)
async def register_user(
    data: VerifyEmailInputDTO,
    service: VerifyEmailService = Depends(get_verify_email_service)
):
    try:
        return await service.verify_email(data)
    except DomainError as e:
        raise HTTPException(400, str(e))
