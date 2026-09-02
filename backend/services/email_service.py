from __future__ import annotations

import logging
import os
import smtplib
from email.message import EmailMessage

logger = logging.getLogger("testpilot.email")


def email_delivery_configured() -> bool:
    return bool(os.getenv("SMTP_HOST") and os.getenv("SMTP_FROM"))


def debug_tokens_enabled() -> bool:
    return (
        os.getenv("AUTH_DEBUG_TOKENS", "false").lower() == "true"
        and os.getenv("ENVIRONMENT", "development").lower() != "production"
    )


def frontend_base_url() -> str:
    return os.getenv("FRONTEND_BASE_URL", "http://localhost:5173").rstrip("/")


def send_password_reset_email(email: str, token: str) -> bool:
    link = f"{frontend_base_url()}/reset-password?token={token}"
    return _send_email(
        email,
        "Reset your TestPilot AI password",
        (
            "Use the secure link below to reset your TestPilot AI password. "
            "The link expires soon and can be used only once.\n\n"
            f"{link}\n\n"
            "If you did not request this, you can ignore this message."
        ),
    )


def send_magic_link_email(email: str, token: str) -> bool:
    link = f"{frontend_base_url()}/magic-link?token={token}"
    return _send_email(
        email,
        "Your TestPilot AI sign-in link",
        (
            "Use the secure link below to sign in to TestPilot AI. "
            "The link expires soon and can be used only once.\n\n"
            f"{link}\n\n"
            "If you did not request this, you can ignore this message."
        ),
    )


def _send_email(to_email: str, subject: str, body: str) -> bool:
    if not email_delivery_configured():
        logger.warning("Email delivery requested but SMTP configuration is incomplete.")
        return False

    message = EmailMessage()
    message["From"] = os.getenv("SMTP_FROM", "")
    message["To"] = to_email
    message["Subject"] = subject
    message.set_content(body)

    host = os.getenv("SMTP_HOST", "")
    port = int(os.getenv("SMTP_PORT", "587"))
    username = os.getenv("SMTP_USERNAME")
    password = os.getenv("SMTP_PASSWORD")
    use_tls = os.getenv("SMTP_USE_TLS", "true").lower() == "true"

    try:
        with smtplib.SMTP(host, port, timeout=12) as server:
            if use_tls:
                server.starttls()
            if username and password:
                server.login(username, password)
            server.send_message(message)
        return True
    except Exception:
        logger.exception("Email delivery failed for %s.", subject)
        return False
