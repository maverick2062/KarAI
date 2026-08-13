import enum
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, LargeBinary, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models.common import generate_uuid, utcnow


class ReportType(str, enum.Enum):
    PDF = "pdf"
    EXCEL = "excel"


class Report(Base):
    __tablename__ = "reports"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    report_type: Mapped[ReportType] = mapped_column(Enum(ReportType), nullable=False)
    financial_year: Mapped[str] = mapped_column(String(7), nullable=False)

    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_bytes: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)

    dataset_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    rule_table_version: Mapped[str] = mapped_column(String(64), nullable=False)

    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    owner: Mapped["User"] = relationship()
