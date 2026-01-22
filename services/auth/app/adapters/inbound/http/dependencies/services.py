from fastapi import Depends

from app.adapters.outbound.persistence.sqlalchemy.transaction import SQLAlchemyTransaction
from app.adapters.outbound.persistence.sqlalchemy.repositories.user import UserRepository
from app.adapters.outbound.persistence.sqlalchemy.repositories.email_verification_token import EmailVerificationTokenRepository
from app.adapters.config import SettingsConfigPort
from app.application.use_cases.register_user import RegistrationService
from app.application.use_cases.verify_email import VerifyEmailService

from .db import get_transaction
from .repositories import get_user_repo, get_token_repo
from .config import get_config


def get_registration_service(
    tx: SQLAlchemyTransaction = Depends(get_transaction),
    user_repo: UserRepository = Depends(get_user_repo),
    token_repo: EmailVerificationTokenRepository = Depends(get_token_repo),
    config: SettingsConfigPort = Depends(get_config),
) -> RegistrationService:
    return RegistrationService(tx, user_repo, token_repo, config)

def get_verify_email_service(
    tx: SQLAlchemyTransaction = Depends(get_transaction),
    user_repo: UserRepository = Depends(get_user_repo),
    token_repo: EmailVerificationTokenRepository = Depends(get_token_repo),
) -> VerifyEmailService:
    return VerifyEmailService(tx, user_repo, token_repo)