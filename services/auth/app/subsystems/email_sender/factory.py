from app.repositories import EmailOutboxRepository
from app.models import EmailOutbox, User

from .type import EmailType
from .payloads import VerifyEmailPayload


class EmailFactory:

    @staticmethod
    async def verification_email(user: User, payload: VerifyEmailPayload, email_outbox_repo: EmailOutboxRepository):
        
        email_obj = EmailOutbox.create(
            user_id=user.user_id,
            email_type=EmailType.VERIFY_EMAIL,
            email=user.email,
            payload=payload.model_dump(),
        )

        await email_outbox_repo.add(email_obj)