import uuid
from datetime import datetime, timezone


def generate_uuid() -> str:
    """Plain string UUIDs (not the Postgres-native UUID type) so models work
    identically against Postgres (production/Docker) and SQLite (fast unit
    tests) without a dialect-specific column type."""
    return str(uuid.uuid4())


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def current_financial_year(as_of: datetime | None = None) -> str:
    """Indian financial year runs 1 April - 31 March, formatted "2026-27"."""
    moment = as_of or utcnow()
    if moment.month >= 4:
        start_year = moment.year
    else:
        start_year = moment.year - 1
    return f"{start_year}-{str(start_year + 1)[-2:]}"
