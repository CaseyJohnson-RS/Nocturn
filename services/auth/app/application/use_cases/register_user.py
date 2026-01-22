from app.application.dto.register_user import (
    RegisterUserInputDTO,
    RegisterUserOutputDTO,
)
from app.application.services import TransactionPort

from app.domain.exceptions import UserAlreadyExists
from app.domain.models import EmailVerificationToken, User
from app.domain.ports.config import ConfigPort
from app.domain.ports.repositories import (
    EmailVerificationTokenRepository,
    UserRepository,
)


class RegistrationService:
    def __init__(
        self,
        tx: TransactionPort,
        users: UserRepository,
        email_tokens: EmailVerificationTokenRepository,
        config: ConfigPort,
    ):
        self.tx = tx
        self.users = users
        self.email_tokens = email_tokens
        self.config = config

    async def register(self, data: RegisterUserInputDTO) -> RegisterUserOutputDTO:
        async with self.tx:
            # 1. Check user exsists and email verified
            user = await self.users.get_user_by_email(data.email)
            if user and user.is_email_verified:
                raise UserAlreadyExists()

            # 2. Create user or update data
            if user:
                user.update(
                    password=data.password,
                    username=data.username
                )
            else:
                user = User.register(
                    email=data.email,
                    username=data.username,
                    password=data.password,
                )
            await self.users.save(user)

            # 3. Create email verification token and add to database
            token, token_string = EmailVerificationToken.create(
                user_id=user.id,
                token_length=self.config.get_email_token_length(),
                expiry=self.config.get_email_token_expiry()
            )
            await self.email_tokens.save(token)

            # TODO:
            # 4. Send token on email
            # 5. Audit logging

            return RegisterUserOutputDTO(
                id=user.id, email=user.email, verification_email_enqueued=True
            )
