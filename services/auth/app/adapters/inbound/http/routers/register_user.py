from fastapi import APIRouter, Depends, HTTPException
from app.application.dto.register_user import RegisterUserInputDTO, RegisterUserOutputDTO
from app.adapters.inbound.http.dependencies import get_registration_service
from app.application.use_cases.register_user import RegistrationService
from app.domain.exceptions import DomainError

router = APIRouter()

@router.post("/", response_model=RegisterUserOutputDTO)
async def register_user(
    data: RegisterUserInputDTO,
    service: RegistrationService = Depends(get_registration_service)
):
    try:
        return await service.register(data)
    except DomainError as e:
        raise HTTPException(400, str(e))
