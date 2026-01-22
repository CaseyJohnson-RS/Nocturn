import uuid
import pytest

from app.domain.models.user import User, UserStatus
from app.domain.exceptions import EmailAlreadyVerified

from app.utils.security import verify_password

def test_register_creates_user():
    email = "test@example.com"
    password = "secret"
    username = "tester"

    user = User.register(email=email, password=password, username=username)

    assert isinstance(user.id, uuid.UUID)
    assert user.email == email
    assert user.username == username
    assert user.status == UserStatus.ACTIVE
    assert not user.is_email_verified
    assert verify_password(password, user.password_hash)


def test_verify_email_marks_verified():
    user = User.register("a@b.com", "pwd")
    assert not user.is_email_verified

    user.verify_email()
    assert user.is_email_verified

def test_verify_email_already_verified_raises():
    user = User.register("a@b.com", "pwd")
    user.is_email_verified = True

    with pytest.raises(EmailAlreadyVerified):
        user.verify_email()

def test_update_password_and_username():
    user = User.register("a@b.com", "pwd", "oldname")

    user.update(password="newpwd", username="newname")

    assert user.username == "newname"
    assert verify_password("newpwd", user.password_hash)

def test_update_partial():
    user = User.register("a@b.com", "pwd", "oldname")

    # Меняем только username
    user.update(username="newname")
    assert user.username == "newname"
    # Пароль не меняется
    assert verify_password("pwd", user.password_hash)

    # Меняем только пароль
    user.update(password="newpwd")
    assert verify_password("newpwd", user.password_hash)

