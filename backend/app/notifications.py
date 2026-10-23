"""Email notifications for account and TDS events."""

import logging
import smtplib
import ssl
from email.message import EmailMessage

from app.config import get_settings
settings = get_settings()
logger = logging.getLogger("karai.notifications")


def send_email(to: str, subject: str, body: str) -> None:
    if not settings.smtp_host or not settings.smtp_from_email:
        logger.warning("Email not sent to %s: configure SMTP_HOST and SMTP_FROM_EMAIL.", to)
        return
    username = settings.smtp_username
    password = settings.smtp_password
    if bool(username) != bool(password):
        logger.error("Email not sent to %s: configure both SMTP_USERNAME and SMTP_PASSWORD.", to)
        return

    message = EmailMessage()
    message["From"] = settings.smtp_from_email
    message["To"] = to
    message["Subject"] = subject
    message.set_content(body)

    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10) as server:
            server.ehlo()
            if settings.smtp_starttls:
                server.starttls(context=ssl.create_default_context())
                server.ehlo()
            if username and password:
                server.login(username, password)
            server.send_message(message)
    except (OSError, smtplib.SMTPException):
        logger.exception("Failed to send email to %s.", to)


def send_tds_event_email(to: str, events: list[dict[str, str]]) -> None:
    """Send one concise alert for all TDS-applicable events in an ingestion run."""
    lines = ["TDS was flagged for the following payment(s):", ""]
    for event in events:
        lines.append(
            f"- {event['vendor']}: {event['category']}; "
            f"TDS ₹{event['tds_amount']} at {event['rate_percent']}%{event['pan_note']}."
        )
    lines.extend(("", "Open KarAI to review the event details and filing deadline."))
    send_email(to, "KarAI: TDS event detected", "\n".join(lines))
