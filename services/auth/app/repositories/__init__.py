from app.core.db import postgres_async_session_factory

from .user import UserRepository
from .email_verification_token import EmailVerificationTokenRepository
from .sent_email import SentEmailRepository


class UnitOfWork:
    def __init__(self):
        self._session_factory = postgres_async_session_factory

    async def __aenter__(self):
        self.session = self._session_factory()
        await self.session.__aenter__()
        self.tx = self.session.begin()
        await self.tx.__aenter__()

        self.users = UserRepository(self.session)
        self.email_tokens = EmailVerificationTokenRepository(self.session)
        self.email_outbox = SentEmailRepository(self.session)
        # self.security_events = 

        return self

    async def __aexit__(self, exc_type, exc, tb):
        await self.tx.__aexit__(exc_type, exc, tb)
        await self.session.__aexit__(exc_type, exc, tb)