import enum
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Boolean, Date, DateTime, Enum, ForeignKey, Index, JSON, Numeric, String
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
    __table_args__ = (
        Index("ix_transactions_user_amount", "user_id", "amount"),
        Index("ix_transactions_user_date_id", "user_id", "transaction_date", "id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    vendor_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("vendors.id", ondelete="SET NULL"), nullable=True, index=True)

    source_type: Mapped[TransactionSourceType] = mapped_column(Enum(TransactionSourceType), nullable=False)
    external_ref: Mapped[str | None] = mapped_column(String(255), nullable=True)

    transaction_date: Mapped[date] = mapped_column(Date, nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    description: Mapped[str | None] = mapped_column(EncryptedString, nullable=True)
    declared_category: Mapped[str | None] = mapped_column(String(64), nullable=True)
    rule_context: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    is_completed: Mapped[bool] = mapped_column(
        "is_completed", Boolean(), nullable=False, default=False, server_default="false"
    )
    is_deleted: Mapped[bool] = mapped_column(
        "is_deleted", Boolean(), nullable=False, default=False, server_default="false"
    )

    financial_year: Mapped[str] = mapped_column(String(7), nullable=False, default=current_financial_year)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    owner: Mapped["User"] = relationship(back_populates="transactions")
    vendor: Mapped["Vendor | None"] = relationship(back_populates="transactions")
    tds_event: Mapped["TDSEvent | None"] = relationship(back_populates="transaction", uselist=False, cascade="all, delete-orphan")

    @property
    def tds_applicable(self) -> bool:
        return bool(self.tds_event and self.tds_event.tds_applicable)

    @property
    def tds_amount(self) -> Decimal | None:
        return self.tds_event.tds_amount if self.tds_event else None

    @property
    def party_name(self) -> str | None:
        return self.vendor.name if self.vendor else None
