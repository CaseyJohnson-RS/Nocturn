import uuid
from typing import Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from app.domain.exceptions import (
    EmailDoesNotMatchToken,
    TokenAlreadyUsed,
    TokenExpired,
)
from .user import User
from app.utils.time import utc_now
from app.utils.security import generate_token, hash_token


@dataclass
class EmailVerificationToken:
    id: uuid.UUID
    token_hash: str
    user_id: uuid.UUID
    user: User
    expires_at: datetime
    used: bool = field(default=False)

    @classmethod
    def create(
        cls,
        user: User,
        token_length: int,
        expiry: timedelta,
    ) -> Tuple["EmailVerificationToken", str]:
        token_str = generate_token(token_length)
        token_hash_val = hash_token(token_str)
        expires_at = utc_now() + expiry

        token = cls(
            id=uuid.uuid4(),
            token_hash=token_hash_val,
            user_id=user.id,
            user=user,
            expires_at=expires_at,
            used=False,
        )
        return token, token_str

    def mark_as_used(self) -> None:
        self.used = True

    def validate(self, email: str) -> None:
        if self.used:
            raise TokenAlreadyUsed()
        if self.expires_at < utc_now():
            raise TokenExpired()
        if self.user.email != email:
            raise EmailDoesNotMatchToken()
