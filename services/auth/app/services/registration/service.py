from app.services.registration.schemas import (
    RegisterUserSchema,
    VerifyEmailRequest,
)

from app.core.settings import settings
from app.core.security import hash_password, generate_token, hash_token
from app.core.time import utc_now

from app.models import EmailVerificationToken, User

from app.repositories import UnitOfWork

from app.subsystems.email_sender import EmailOutboxCreator
from app.subsystems.email_sender.payloads import VerifyEmailPayload

from app.services.registration.dto import RegistrationResult, VerifyEmailResult

from app.services.registration.exceptions import (
    UserAlreadyExists,
    InvalidEmailToken,
    ExpiredEmailToken,
    EmailDoesNotMatchToken
)


class RegistrationService:
    @staticmethod
    async def register_user(data: RegisterUserSchema) -> RegistrationResult:
        async with UnitOfWork() as uow:

            # 1. Check if user exists
            user = await uow.users.get_user_by_email(data.email)
            if user:
                raise UserAlreadyExists()
            
            # 2. Create user and add to the database
            user = User.create(
                email=data.email,
                username=data.username,
                password_hash=hash_password(data.password)
            )
            await uow.users.add(user)

            # 3. Create email verification token and add to the database
            token_str = generate_token(settings.email_token_length)
            token = EmailVerificationToken.create(
                token_hash=hash_token(token_str),
                user_id=user.user_id,
                expires_at=utc_now() + settings.email_token_expiry
            )
            await uow.email_tokens.add(token)

            # 4. Create email notification
            await EmailOutboxCreator.verification_email(
                user=user, 
                payload=VerifyEmailPayload(
                    username=user.username,
                    token=token_str
                ),
                email_outbox_repo=uow.email_outbox
            )

            return RegistrationResult(
                user_id=user.user_id,
                email=user.email,
                verification_email_enqueued=True
            )

    @staticmethod
    async def verify_email(data: VerifyEmailRequest) -> VerifyEmailResult:
        async with UnitOfWork() as uow:

            # 1. Retrieve token from the database
            token = await uow.email_tokens.get_token_by_hash(hash_token(data.token))

            # 2. Check if token exists
            if not token:
                raise InvalidEmailToken()

            # 3. Check token expires
            if token.expires_at < utc_now():
                raise ExpiredEmailToken()

            # 4. Check email matches the token's user
            if token.user.email != data.email:
                raise EmailDoesNotMatchToken()
            
            # 5. Mark user's email as verified
            await uow.users.set_email_verified(token.user)

            # 6. Mark token as used
            await uow.email_tokens.mark_token_used(token)

            return VerifyEmailResult(
                user_id=token.user.user_id,
                email=token.user.email,
                token_used=True
            )
