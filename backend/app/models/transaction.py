import enum
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, Enum, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models.common import current_financial_year, generate_uuid, utcnow
from app.models.types import EncryptedString


class TransactionSourceType(str, enum.Enum):
    CSV_UPLOAD = "csv_upload"
    MANUAL_ENTRY = "manual_entry"
    SYNTHETIC_FEED = "synthetic_feed"
    ACCOUNT_AGGREGATOR = "account_aggregator"  # reserved for the real AA integration


class Transaction(Base):
    __tablename__ = "transactions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    vendor_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("vendors.id", ondelete="SET NULL"), nullable=True, index=True)

    source_type: Mapped[TransactionSourceType] = mapped_column(Enum(TransactionSourceType), nullable=False)
    external_ref: Mapped[str | None] = mapped_column(String(255), nullable=True)

    transaction_date: Mapped[date] = mapped_column(Date, nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    description: Mapped[str | None] = mapped_column(EncryptedString, nullable=True)
    declared_category: Mapped[str | None] = mapped_column(String(64), nullable=True)

    financial_year: Mapped[str] = mapped_column(String(7), nullable=False, default=current_financial_year)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    owner: Mapped["User"] = relationship(back_populates="transactions")
    vendor: Mapped["Vendor | None"] = relationship(back_populates="transactions")
    tds_event: Mapped["TDSEvent | None"] = relationship(back_populates="transaction", uselist=False, cascade="all, delete-orphan")
