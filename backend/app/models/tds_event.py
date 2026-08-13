from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models.common import generate_uuid, utcnow
from app.rule_engine.section_393 import TDSCategory


class TDSEvent(Base):
    """The output of running the rule engine + tds_detector on a transaction."""

    __tablename__ = "tds_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    transaction_id: Mapped[str] = mapped_column(String(36), ForeignKey("transactions.id", ondelete="CASCADE"), nullable=False, unique=True)

    category: Mapped[TDSCategory] = mapped_column(Enum(TDSCategory), nullable=False)
    rule_table_version: Mapped[str] = mapped_column(String(64), nullable=False)

    threshold_crossed_this_transaction: Mapped[bool] = mapped_column(Boolean, nullable=False)
    tds_applicable: Mapped[bool] = mapped_column(Boolean, nullable=False)

    cumulative_before: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    cumulative_after: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    taxable_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    tds_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    rate_percent: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)

    explanation_text: Mapped[str] = mapped_column(Text, nullable=False)
    filing_form_reference: Mapped[str | None] = mapped_column(String(255), nullable=True)
    filing_deadline: Mapped[str | None] = mapped_column(String(32), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    transaction: Mapped["Transaction"] = relationship(back_populates="tds_event")
