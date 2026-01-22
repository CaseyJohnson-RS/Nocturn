from typing import Protocol


class TransactionPort(Protocol):

    async def __aenter__(self) -> None:
        pass

    async def __aexit__(self, exc_type, exc, tb) -> None:
        pass
