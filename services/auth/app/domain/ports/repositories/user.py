import uuid
from typing import Protocol

from app.domain.models import User


class UserRepository(Protocol):
    
    async def get_user_by_email(self, email: str) -> User | None:
        pass

    async def get_user_by_id(self, id: uuid.UUID):
        pass
    
    async def save(self, user: User):
        pass

    async def delete(self, user: User):
        pass