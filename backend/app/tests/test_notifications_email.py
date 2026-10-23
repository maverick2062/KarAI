from email.message import EmailMessage

from app import notifications


class FakeSMTP:
    last_instance = None

    def __init__(self, host, port, timeout):
        self.host = host
        self.port = port
        self.timeout = timeout
        self.sent_message: EmailMessage | None = None
        self.logged_in = False
        self.started_tls = False
        type(self).last_instance = self

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def ehlo(self):
        pass

    def starttls(self, context):
        self.started_tls = True

    def login(self, username, password):
        self.logged_in = True

    def send_message(self, message):
        self.sent_message = message


def test_send_email_uses_configured_smtp(monkeypatch):
    monkeypatch.setattr(notifications, "settings", notifications.settings.model_copy(update={
        "smtp_host": "mail.example.test",
        "smtp_port": 587,
        "smtp_username": "karai",
        "smtp_password": "test-password",
        "smtp_from_email": "alerts@example.test",
        "smtp_starttls": True,
    }))
    monkeypatch.setattr(notifications.smtplib, "SMTP", FakeSMTP)

    notifications.send_email("user@example.test", "TDS alert", "TDS was flagged.")

    assert FakeSMTP.last_instance is not None
    assert FakeSMTP.last_instance.sent_message is not None
    assert FakeSMTP.last_instance.sent_message["To"] == "user@example.test"
    assert FakeSMTP.last_instance.sent_message["Subject"] == "TDS alert"
    assert FakeSMTP.last_instance.started_tls is True
    assert FakeSMTP.last_instance.logged_in is True
    assert "TDS was flagged." in FakeSMTP.last_instance.sent_message.get_content()


def test_send_email_logs_when_smtp_is_not_configured(monkeypatch, caplog):
    monkeypatch.setattr(notifications, "settings", notifications.settings.model_copy(update={
        "smtp_host": None,
        "smtp_from_email": None,
    }))

    notifications.send_email("user@example.test", "TDS alert", "TDS was flagged.")

    assert "Email not sent" in caplog.text


def test_tds_alert_includes_rate_and_missing_pan_status(monkeypatch):
    captured = {}

    def capture_email(to, subject, body):
        captured.update(to=to, subject=subject, body=body)

    monkeypatch.setattr(notifications, "send_email", capture_email)
    notifications.send_tds_event_email(
        "user@example.test",
        [{
            "vendor": "Acme Services",
            "category": "professional fees",
            "tds_amount": "8,000.00",
            "rate_percent": "20",
            "pan_note": " (PAN not furnished)",
        }],
    )

    assert captured["to"] == "user@example.test"
    assert captured["subject"] == "KarAI: TDS event detected"
    assert "TDS ₹8,000.00 at 20% (PAN not furnished)" in captured["body"]
