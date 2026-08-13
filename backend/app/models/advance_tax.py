import enum
from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models.common import generate_uuid, utcnow


class TaxRegime(str, enum.Enum):
    OLD = "old"
    NEW = "new"


class AdvanceTaxEstimate(Base):
    __tablename__ = "advance_tax_estimates"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    financial_year: Mapped[str] = mapped_column(String(7), nullable=False)
    quarter: Mapped[int] = mapped_column(Integer, nullable=False)  # 1-4, per Q1..Q4 installment schedule
    regime: Mapped[TaxRegime] = mapped_column(Enum(TaxRegime), nullable=False)

    total_income_estimate: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    tax_liability: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    installment_due: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    interest_234b: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=Decimal("0"), nullable=False)
    interest_234c: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=Decimal("0"), nullable=False)

    slab_version: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    owner: Mapped["User"] = relationship()
