import enum
import uuid
from dataclasses import dataclass
from datetime import datetime

from app.domain.exceptions import EmailAlreadyVerified
from app.utils.security import hash_password
from app.utils.time import utc_now


class UserStatus(str, enum.Enum):
    ACTIVE = "active"
    BLOCKED = "blocked"


@dataclass
class User:
    id: uuid.UUID
    email: str
    password_hash: str
    username: str
    status: UserStatus
    is_email_verified: bool
    created_at: datetime

    @classmethod
    def register(cls, email: str, password: str, username: str = "Unknown") -> "User":
        return cls(
            id=uuid.uuid4(),
            email=email,
            password_hash=hash_password(password),
            username=username,
            status=UserStatus.ACTIVE,
            is_email_verified=False,
            created_at=utc_now(),
        )

    def verify_email(self):
        if self.is_email_verified:
            raise EmailAlreadyVerified()
        self.is_email_verified = True

    def update(self, password: str | None = None, username: str | None = None):
        self.password_hash = hash_password(password) if password else self.password_hash
        self.username = username if username else self.username