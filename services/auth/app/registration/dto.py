from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class RegistrationResult:
    user_id: UUID
    email: str
    verification_email_enqueued: bool

@dataclass(frozen=True)
class VerifyEmailResult:
    user_id: UUID
    email: str
    token_used: bool
