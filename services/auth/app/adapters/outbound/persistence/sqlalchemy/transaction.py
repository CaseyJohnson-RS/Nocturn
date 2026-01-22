from app.application.services import TransactionPort


class SQLAlchemyTransaction(TransactionPort):
    def __init__(self, session):
        self.session = session

    async def __aenter__(self):
        await self.session.__aenter__()
        self.tx = self.session.begin()
        await self.tx.__aenter__()

    async def __aexit__(self, exc_type, exc, tb):
        await self.tx.__aexit__(exc_type, exc, tb)
        await self.session.__aexit__(exc_type, exc, tb)
