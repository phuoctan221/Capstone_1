"""Small SMTP adapter; blocking smtplib runs outside FastAPI's event loop."""
from __future__ import annotations

import asyncio
import smtplib
from email.message import EmailMessage

from app.core.config import settings


def smtp_is_configured() -> bool:
    return bool(settings.SMTP_USERNAME and settings.SMTP_APP_PASSWORD)


def _send_password_reset_email_sync(email: str, otp: str) -> None:
    if not smtp_is_configured():
        raise RuntimeError("SMTP is not configured")
    message = EmailMessage()
    message["Subject"] = "SmartVOCAB AI password reset code"
    message["From"] = f"{settings.SMTP_FROM_NAME} <{settings.SMTP_FROM_EMAIL or settings.SMTP_USERNAME}>"
    message["To"] = email
    message.set_content(
        f"Your SmartVOCAB AI password reset code is: {otp}\n\n"
        f"It expires in {settings.PASSWORD_RESET_OTP_TTL_MINUTES} minutes. "
        "If you did not request this, you can ignore this email."
    )
    with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=15) as server:
        server.starttls()
        server.login(settings.SMTP_USERNAME, settings.SMTP_APP_PASSWORD)
        server.send_message(message)


async def send_password_reset_email(email: str, otp: str) -> None:
    await asyncio.to_thread(_send_password_reset_email_sync, email, otp)