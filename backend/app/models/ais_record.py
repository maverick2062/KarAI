import enum
from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, Enum, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models.common import generate_uuid, utcnow


class AISSourceType(str, enum.Enum):
    SYNTHETIC = "synthetic"
    USER_UPLOAD = "user_upload"
    OAUTH_PULL = "oauth_pull"  # reserved for the real IT-portal AIS OAuth integration


class AISRecord(Base):
    """A single line from the user's (mocked) Annual Information Statement,
    used to detect discrepancies against self-reported transactions."""

    __tablename__ = "ais_records"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    source_type: Mapped[AISSourceType] = mapped_column(Enum(AISSourceType), nullable=False)
    financial_year: Mapped[str] = mapped_column(String(7), nullable=False)
    reporting_entity: Mapped[str] = mapped_column(String(255), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    category: Mapped[str] = mapped_column(String(64), nullable=False)
    raw_payload: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    owner: Mapped["User"] = relationship()
