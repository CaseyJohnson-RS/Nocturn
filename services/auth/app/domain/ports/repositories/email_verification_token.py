from typing import Protocol

from app.domain.models import EmailVerificationToken


class EmailVerificationTokenRepository(Protocol):

    async def get_token_by_string(self, token_string: str) -> EmailVerificationToken | None:
        pass

    async def save(self, token: EmailVerificationToken):
        pass
        
    async def delete(self, token: EmailVerificationToken):
        pass
