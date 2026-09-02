from __future__ import annotations

import logging
import os
import smtplib
from email.message import EmailMessage

logger = logging.getLogger("testpilot.email")


def email_delivery_configured() -> bool:
    return bool(os.getenv("SMTP_HOST") and os.getenv("SMTP_FROM"))


def send_password_reset_code_email(email: str, code: str) -> bool:
    return _send_email(
        email,
        "Your TestPilot AI password reset code",
        (
            "Use this one-time verification code to reset your TestPilot AI password:\n\n"
            f"{code}\n\n"
            "The code expires soon and can be used only once. "
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
