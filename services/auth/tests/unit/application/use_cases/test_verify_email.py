import pytest
from unittest.mock import AsyncMock
from uuid import uuid4

from app.application.use_cases.verify_email import VerifyEmailService
from app.application.dto.verify_email import VerifyEmailInputDTO
from app.domain.models import User, EmailVerificationToken
from app.domain.exceptions import InvalidToken, UserDoesNotExist

@pytest.mark.asyncio
async def test_verify_email_success():
    user = User.register("a@b.com", "password", "u1")
    token = EmailVerificationToken(
        id=uuid4(),
        token_hash="hash",
        user_id=user.id,
        expires_at=user.created_at.replace(year=user.created_at.year + 1),
        used=False
    )

    tx = AsyncMock()
    users_repo = AsyncMock()
    email_tokens_repo = AsyncMock()

    users_repo.get_user_by_email.return_value = user
    email_tokens_repo.get_token_by_string.return_value = token

    service = VerifyEmailService(tx, users_repo, email_tokens_repo)
    data = VerifyEmailInputDTO(email="a@b.com", token="tokenstring")

    output = await service.verify_email(data)

    assert output.email == "a@b.com"
    assert output.token_used is True
    assert user.is_email_verified is True
    assert token.used is True

    users_repo.save.assert_awaited_with(user)
    email_tokens_repo.save.assert_awaited_with(token)

@pytest.mark.asyncio
async def test_verify_email_invalid_token():
    tx = AsyncMock()
    users_repo = AsyncMock()
    email_tokens_repo = AsyncMock()

    email_tokens_repo.get_token_by_string.return_value = None
    users_repo.get_user_by_email.return_value = User.register("a@b.com", "password", "u1")

    service = VerifyEmailService(tx, users_repo, email_tokens_repo)
    data = VerifyEmailInputDTO(email="a@b.com", token="badtoken")

    with pytest.raises(InvalidToken):
        await service.verify_email(data)

@pytest.mark.asyncio
async def test_verify_email_user_does_not_exist():
    tx = AsyncMock()
    users_repo = AsyncMock()
    email_tokens_repo = AsyncMock()

    token = EmailVerificationToken(
        id=uuid4(),
        token_hash="hash",
        user_id=uuid4(),
        expires_at=None,
        used=False
    )
    email_tokens_repo.get_token_by_string.return_value = token
    users_repo.get_user_by_email.return_value = None

    service = VerifyEmailService(tx, users_repo, email_tokens_repo)
    data = VerifyEmailInputDTO(email="a@b.com", token="tokenstring")

    with pytest.raises(UserDoesNotExist):
        await service.verify_email(data)

@pytest.mark.asyncio
async def test_verify_email_token_already_used():
    user = User.register("a@b.com", "password", "u1")
    token = EmailVerificationToken(
        id=uuid4(),
        token_hash="hash",
        user_id=user.id,
        expires_at=user.created_at.replace(year=user.created_at.year + 1),
        used=True
    )

    tx = AsyncMock()
    users_repo = AsyncMock()
    email_tokens_repo = AsyncMock()

    users_repo.get_user_by_email.return_value = user
    email_tokens_repo.get_token_by_string.return_value = token

    service = VerifyEmailService(tx, users_repo, email_tokens_repo)
    data = VerifyEmailInputDTO(email="a@b.com", token="tokenstring")

    from app.domain.exceptions import TokenAlreadyUsed
    with pytest.raises(TokenAlreadyUsed):
        await service.verify_email(data)
