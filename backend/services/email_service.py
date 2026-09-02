from __future__ import annotations

import logging
import os
import smtplib
import ssl
from email.message import EmailMessage

logger = logging.getLogger("testpilot.email")


def email_delivery_configured() -> bool:
    host = os.getenv("SMTP_HOST", "")
    if host.lower() == "smtp.gmail.com":
        return bool(host and os.getenv("SMTP_FROM") and os.getenv("SMTP_USERNAME") and os.getenv("SMTP_PASSWORD"))
    return bool(host and os.getenv("SMTP_FROM"))


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
            server.ehlo()
            if use_tls:
                server.starttls(context=ssl.create_default_context())
                server.ehlo()
            if username and password:
                server.login(username, password)
            server.send_message(message)
        return True
    except Exception as exc:
        logger.exception(
            "Email delivery failed for subject '%s' (host_configured=%s, port=%s, tls=%s, auth_configured=%s, from_configured=%s, error_type=%s).",
            subject,
            bool(host),
            port,
            use_tls,
            bool(username and password),
            bool(os.getenv("SMTP_FROM")),
            exc.__class__.__name__,
        )
        return False
