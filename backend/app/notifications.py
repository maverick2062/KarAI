"""Transactional notifications (account lockout, OTP, report-ready emails).

Prototype implementation logs the notification instead of sending real email —
no SMTP credentials exist for this project. Swap `send_email`'s body for a
real SMTP/SES call when deploying; every call site already passes the
complete (to, subject, body) it would need.
"""

import logging

logger = logging.getLogger("karai.notifications")


def send_email(to: str, subject: str, body: str) -> None:
    logger.info("EMAIL (not actually sent — no SMTP configured) to=%s subject=%r body=%r", to, subject, body)
