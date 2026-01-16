from sqlalchemy.ext.asyncio import AsyncSession

from app.models import EmailOutbox

class EmailOutboxRepository:

    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def add(self, email: EmailOutbox):
        self.session.add(email)