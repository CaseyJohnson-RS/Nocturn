"""Tests for email service."""

from unittest.mock import MagicMock, patch

import pytest

from src.app.common.email import (
    init_email_service,
    send_confirmation_email,
    send_email,
    send_password_reset_email,
)
from src.app.config import settings


@pytest.fixture(autouse=True)
def email_settings(monkeypatch: pytest.MonkeyPatch):
    """Provide valid email settings for every test."""
    monkeypatch.setattr(settings, "email_api_key", "test-api-key")
    monkeypatch.setattr(settings, "email_from", "noreply@nocturn.dev")
    monkeypatch.setattr(settings, "frontend_url", "https://nocturn.dev")
    monkeypatch.setattr(settings, "email_confirm_ttl_hours", 24)
    monkeypatch.setattr(settings, "password_reset_ttl_hours", 1)
    init_email_service()


@pytest.fixture()
def mock_resend():
    with patch("src.app.common.email.resend.Emails.send") as mock_send:
        yield mock_send


# --- init ---


def test_init_sets_api_key():
    import resend

    assert resend.api_key == "test-api-key"


def test_init_no_api_key_logs_warning(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
):
    monkeypatch.setattr(settings, "email_api_key", "")
    init_email_service()
    assert "EMAIL_API_KEY not set" in caplog.text


# --- send_email ---


@pytest.mark.anyio()
async def test_send_email_calls_resend(mock_resend: MagicMock):
    await send_email("user@example.com", "Subject", "<p>body</p>")

    mock_resend.assert_called_once_with(
        {
            "from": "noreply@nocturn.dev",
            "to": "user@example.com",
            "subject": "Subject",
            "html": "<p>body</p>",
        }
    )


@pytest.mark.anyio()
async def test_send_email_raises_when_not_initialised(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(settings, "email_api_key", "")
    with pytest.raises(RuntimeError, match="not initialised"):
        await send_email("user@example.com", "Subject", "<p>body</p>")


@pytest.mark.anyio()
async def test_send_email_propagates_resend_error(mock_resend: MagicMock):
    mock_resend.side_effect = Exception("API error")
    with pytest.raises(Exception, match="API error"):
        await send_email("user@example.com", "Subject", "<p>body</p>")


# --- send_confirmation_email ---


@pytest.mark.anyio()
async def test_confirmation_email_content(mock_resend: MagicMock):
    await send_confirmation_email("user@example.com", "abc123")

    call_args = mock_resend.call_args[0][0]
    assert call_args["to"] == "user@example.com"
    assert "Confirm" in call_args["subject"]
    assert "confirm-email?token=abc123" in call_args["html"]
    assert "24 hours" in call_args["html"]


@pytest.mark.anyio()
async def test_confirmation_email_escapes_token(mock_resend: MagicMock):
    await send_confirmation_email("user@example.com", '<script>alert("xss")</script>')

    html = mock_resend.call_args[0][0]["html"]
    assert "<script>" not in html
    assert "&lt;script&gt;" in html


# --- send_password_reset_email ---


@pytest.mark.anyio()
async def test_password_reset_email_content(mock_resend: MagicMock):
    await send_password_reset_email("user@example.com", "reset-token")

    call_args = mock_resend.call_args[0][0]
    assert call_args["to"] == "user@example.com"
    assert "Reset" in call_args["subject"]
    assert "reset-password?token=reset-token" in call_args["html"]
    assert "1 hour(s)" in call_args["html"]


@pytest.mark.anyio()
async def test_password_reset_email_escapes_token(mock_resend: MagicMock):
    await send_password_reset_email("user@example.com", '" onclick="alert(1)')

    html = mock_resend.call_args[0][0]["html"]
    assert '" onclick=' not in html
    assert "&quot;" in html
