"""Email service (Resend)."""

import asyncio
import functools
import logging
from html import escape

import resend

from src.app.config import settings

logger = logging.getLogger(__name__)


def init_email_service() -> None:
    """Call once during application startup."""
    if not settings.email_api_key:
        logger.warning("EMAIL_API_KEY not set — email service disabled")
        return
    resend.api_key = settings.email_api_key


async def _send(to: str, subject: str, html: str) -> None:
    fn = functools.partial(
        resend.Emails.send,
        {"from": settings.email_from, "to": to, "subject": subject, "html": html},
    )
    await asyncio.to_thread(fn)


async def send_email(to: str, subject: str, html: str) -> None:
    if not settings.email_api_key:
        raise RuntimeError("Email service not initialised — call init_email_service() first")

    await _send(to, subject, html)
    logger.info("Email sent to %s", to)


# --- Templates ---


def _base_html(body: str) -> str:
    return (
        '<div style="font-family: -apple-system, sans-serif; max-width: 480px;'
        ' margin: 0 auto; padding: 32px;">'
        '<h2 style="color: #1a1a2e;">Nocturn</h2>'
        f"{body}"
        '<hr style="border: none; border-top: 1px solid #eee; margin: 24px 0;">'
        '<p style="color: #999; font-size: 12px;">'
        "You received this email because of your Nocturn account."
        "</p></div>"
    )


def _action_email(text: str, button_text: str, link: str, footer: str) -> str:
    safe_link = escape(link, quote=True)
    return _base_html(
        f"<p>{text}</p>"
        f'<p><a href="{safe_link}" style="display: inline-block; background: #1a1a2e;'
        f' color: #fff; padding: 12px 24px; border-radius: 6px; text-decoration: none;">'
        f"{button_text}</a></p>"
        f'<p style="color: #666; font-size: 13px;">Or copy this link: {safe_link}</p>'
        f'<p style="color: #666; font-size: 13px;">{footer}</p>'
    )


async def send_confirmation_email(to: str, token: str) -> None:
    link = f"{settings.frontend_url}/confirm-email?token={token}"
    html = _action_email(
        text="Welcome to Nocturn! Please confirm your email address:",
        button_text="Confirm Email",
        link=link,
        footer=f"This link expires in {settings.email_confirm_ttl_hours} hours.",
    )
    await send_email(to, "Confirm your Nocturn account", html)


async def send_password_reset_email(to: str, token: str) -> None:
    link = f"{settings.frontend_url}/reset-password?token={token}"
    html = _action_email(
        text="You requested a password reset for your Nocturn account:",
        button_text="Reset Password",
        link=link,
        footer=(
            f"This link expires in {settings.password_reset_ttl_hours} hour(s). "
            "If you didn't request this, ignore this email."
        ),
    )
    await send_email(to, "Reset your Nocturn password", html)