from uuid import UUID, uuid4
from typing import Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from app.domain.exceptions import (
    UserDoesNotMatchToken,
    TokenAlreadyUsed,
    TokenExpired,
)
from app.utils.time import utc_now
from app.utils.security import generate_token, hash_token


@dataclass
class EmailVerificationToken:
    id: UUID
    token_hash: str
    user_id: UUID
    expires_at: datetime
    used: bool = field(default=False)

    @classmethod
    def create(
        cls,
        user_id: UUID,
        token_length: int,
        expiry: timedelta,
    ) -> Tuple["EmailVerificationToken", str]:
        token_str = generate_token(token_length)
        token_hash_val = hash_token(token_str)
        expires_at = utc_now() + expiry

        token = cls(
            id=uuid4(),
            token_hash=token_hash_val,
            user_id=user_id,
            expires_at=expires_at,
            used=False,
        )
        return token, token_str

    def mark_as_used(self) -> None:
        self.used = True

    def validate(self, user_id: UUID) -> None:
        if self.used:
            raise TokenAlreadyUsed()
        if self.expires_at < utc_now():
            raise TokenExpired()
        if self.user_id != user_id:
            raise UserDoesNotMatchToken()
