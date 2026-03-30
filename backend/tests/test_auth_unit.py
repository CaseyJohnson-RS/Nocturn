"""Unit tests for auth module — no DB or Redis required."""

import uuid

import pytest

from app.modules.auth.service import AuthService, _hash_token, _validate_password
from app.common.exceptions import UnauthorizedError, ValidationError


class TestPasswordValidation:
    def test_valid_password(self):
        _validate_password("Abcdef1x")

    def test_missing_uppercase(self):
        with pytest.raises(ValidationError):
            _validate_password("abcdef1x")

    def test_missing_lowercase(self):
        with pytest.raises(ValidationError):
            _validate_password("ABCDEF1X")

    def test_missing_digit(self):
        with pytest.raises(ValidationError):
            _validate_password("Abcdefgh")

    def test_all_requirements_met(self):
        _validate_password("MyP4ssword")


class TestTokenHashing:
    def test_deterministic(self):
        token = "some-random-token"
        assert _hash_token(token) == _hash_token(token)

    def test_different_tokens_different_hashes(self):
        assert _hash_token("token-a") != _hash_token("token-b")


class TestJWT:
    def test_create_and_decode(self):
        user_id = uuid.uuid4()
        token = AuthService.create_access_token(user_id, "user")
        payload = AuthService.decode_access_token(token)
        assert payload["sub"] == str(user_id)
        assert payload["role"] == "user"

    def test_decode_invalid_token(self):
        with pytest.raises(UnauthorizedError):
            AuthService.decode_access_token("garbage.token.here")

    def test_payload_contains_exp_and_iat(self):
        user_id = uuid.uuid4()
        token = AuthService.create_access_token(user_id, "admin")
        payload = AuthService.decode_access_token(token)
        assert "exp" in payload
        assert "iat" in payload

    def test_admin_role_preserved(self):
        user_id = uuid.uuid4()
        token = AuthService.create_access_token(user_id, "admin")
        payload = AuthService.decode_access_token(token)
        assert payload["role"] == "admin"
