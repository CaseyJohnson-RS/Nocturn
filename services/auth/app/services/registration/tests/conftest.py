import pytest
from unittest.mock import AsyncMock, MagicMock

@pytest.fixture
def uow_mock(monkeypatch):
    uow = MagicMock()

    uow.__aenter__ = AsyncMock(return_value=uow)
    uow.__aexit__ = AsyncMock(return_value=None)

    uow.users = MagicMock()
    uow.email_tokens = MagicMock()
    uow.email_outbox = MagicMock()

    monkeypatch.setattr(
        "app.services.registration.service.UnitOfWork",
        lambda: uow
    )

    return uow
