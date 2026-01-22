from app.application.dto.verify_email import VerifyEmailInputDTO, VerifyEmailOutputDTO
from app.application.services import TransactionPort

from app.domain.exceptions import InvalidToken, UserDoesNotExist
from app.domain.ports.repositories import EmailVerificationTokenRepository, UserRepository


class VerifyEmailService:

    def __init__(
        self,
        tx: TransactionPort,
        users: UserRepository,
        email_tokens: EmailVerificationTokenRepository,
    ):
        self.tx = tx
        self.users = users
        self.email_tokens = email_tokens

    async def verify_email(self, data: VerifyEmailInputDTO) -> VerifyEmailOutputDTO:
        async with self.tx:
            # 1. Retrieve token and user
            token = await self.email_tokens.get_token_by_string(data.token)
            user = await self.users.get_user_by_email(data.email)

            # 2. Check token exists
            if not token:
                raise InvalidToken()
            
            # 3. Check user exists
            if not user:
                raise UserDoesNotExist()

            # 4. Validate token
            token.validate(user.id)

            # 5. Set email verified
            user.verify_email()
            await self.users.save(user)

            # 6. Mark as used
            token.mark_as_used()
            await self.email_tokens.save(token)

            # TODO
            # Add audit logging

            return VerifyEmailOutputDTO(
                id=user.id,
                email=user.email,
                token_used=True
            )