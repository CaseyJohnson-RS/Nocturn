import pytest
from datetime import timedelta
from uuid import uuid4
from app.domain.models.email_verification_token import EmailVerificationToken
from app.domain.exceptions import TokenAlreadyUsed, TokenExpired, UserDoesNotMatchToken
from app.utils.time import utc_now
from app.utils.security import hash_token

def test_create_token():
    user_id = uuid4()
    expiry = timedelta(hours=1)
    token_obj, token_str = EmailVerificationToken.create(user_id, token_length=16, expiry=expiry)

    assert token_obj.user_id == user_id
    assert not token_obj.used
    assert token_obj.expires_at > utc_now()
    # Проверка, что хеш соответствует токену
    assert token_obj.token_hash == hash_token(token_str)

def test_mark_as_used():
    token_obj, _ = EmailVerificationToken.create(uuid4(), 16, timedelta(hours=1))
    assert not token_obj.used

    token_obj.mark_as_used()
    assert token_obj.used

def test_validate_success():
    user_id = uuid4()
    token_obj, _ = EmailVerificationToken.create(user_id, 16, timedelta(hours=1))
    # Должно пройти без ошибок
    token_obj.validate(user_id)

def test_validate_already_used():
    token_obj, _ = EmailVerificationToken.create(uuid4(), 16, timedelta(hours=1))
    token_obj.mark_as_used()
    with pytest.raises(TokenAlreadyUsed):
        token_obj.validate(token_obj.user_id)

def test_validate_expired():
    user_id = uuid4()
    token_obj, _ = EmailVerificationToken.create(user_id, 16, timedelta(seconds=-1))
    with pytest.raises(TokenExpired):
        token_obj.validate(user_id)

def test_validate_user_mismatch():
    token_obj, _ = EmailVerificationToken.create(uuid4(), 16, timedelta(hours=1))
    wrong_user_id = uuid4()
    with pytest.raises(UserDoesNotMatchToken):
        token_obj.validate(wrong_user_id)
