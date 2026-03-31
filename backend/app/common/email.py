"""Email service with Resend and Brevo provider support."""

import logging

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

_TIMEOUT = httpx.Timeout(15.0, connect=5.0)


async def _send_resend(to: str, subject: str, html: str) -> None:
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        resp = await client.post(
            "https://api.resend.com/emails",
            headers={"Authorization": f"Bearer {settings.email_api_key}"},
            json={
                "from": settings.email_from,
                "to": [to],
                "subject": subject,
                "html": html,
            },
        )
        resp.raise_for_status()


async def _send_brevo(to: str, subject: str, html: str) -> None:
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        resp = await client.post(
            "https://api.brevo.com/v3/smtp/email",
            headers={
                "api-key": settings.email_api_key,
                "Content-Type": "application/json",
            },
            json={
                "sender": {"email": settings.email_from},
                "to": [{"email": to}],
                "subject": subject,
                "htmlContent": html,
            },
        )
        resp.raise_for_status()


_PROVIDERS = {
    "resend": _send_resend,
    "brevo": _send_brevo,
}


async def send_email(to: str, subject: str, html: str) -> None:
    """Send an email using the configured provider.

    Logs a warning and skips if no API key is configured (dev mode).
    """
    if not settings.email_api_key:
        logger.warning("EMAIL_API_KEY not set — skipping email to %s: %s", to, subject)
        return

    provider = _PROVIDERS.get(settings.email_provider)
    if not provider:
        raise ValueError(f"Unknown email provider: {settings.email_provider}")

    await provider(to, subject, html)
    logger.info("Email sent to %s via %s: %s", to, settings.email_provider, subject)


# --- Email templates ---

def _base_html(body: str) -> str:
    return f"""
    <div style="font-family: -apple-system, sans-serif; max-width: 480px; margin: 0 auto; padding: 32px;">
        <h2 style="color: #1a1a2e;">Nocturn</h2>
        {body}
        <hr style="border: none; border-top: 1px solid #eee; margin: 24px 0;">
        <p style="color: #999; font-size: 12px;">You received this email because of your Nocturn account.</p>
    </div>
    """


async def send_confirmation_email(to: str, token: str) -> None:
    link = f"{settings.frontend_url}/confirm-email?token={token}"
    html = _base_html(f"""
        <p>Welcome to Nocturn! Please confirm your email address:</p>
        <p><a href="{link}" style="display: inline-block; background: #1a1a2e; color: #fff;
            padding: 12px 24px; border-radius: 6px; text-decoration: none;">Confirm Email</a></p>
        <p style="color: #666; font-size: 13px;">Or copy this link: {link}</p>
        <p style="color: #666; font-size: 13px;">This link expires in {settings.email_confirm_ttl_hours} hours.</p>
    """)
    await send_email(to, "Confirm your Nocturn account", html)


async def send_password_reset_email(to: str, token: str) -> None:
    link = f"{settings.frontend_url}/reset-password?token={token}"
    html = _base_html(f"""
        <p>You requested a password reset for your Nocturn account:</p>
        <p><a href="{link}" style="display: inline-block; background: #1a1a2e; color: #fff;
            padding: 12px 24px; border-radius: 6px; text-decoration: none;">Reset Password</a></p>
        <p style="color: #666; font-size: 13px;">Or copy this link: {link}</p>
        <p style="color: #666; font-size: 13px;">This link expires in {settings.password_reset_ttl_hours} hour(s).
            If you didn't request this, ignore this email.</p>
    """)
    await send_email(to, "Reset your Nocturn password", html)
