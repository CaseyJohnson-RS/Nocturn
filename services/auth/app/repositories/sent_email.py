from sqlalchemy.ext.asyncio import AsyncSession

from app.models import SentEmail

class SentEmailRepository:

    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def add(self, email: SentEmail):
        self.session.add(email)